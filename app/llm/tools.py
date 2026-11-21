import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import jwt
import psycopg
from google.genai import types
import app.llm.config
from app.rag.tools import check_availability, hotel_photos, create_request, escalate_to_human, REQUEST_TYPES, CATEGORIES
from app.rag.tools import (
    my_bookings, link_booking, find_booking, quote_cancellation, quote_modification,
    late_checkout_quote, check_discount_code, loyalty_status, menu, room_service_quote,
)
from app.llm.knowledge import search_hotel_info

CHECK_AVAILABILITY = types.FunctionDeclaration(
    name="check_availability",
    description="Free rooms and prices for a room type and dates.",
    behavior="NON_BLOCKING",
    parameters={
        "type": "OBJECT",
        "properties": {
            "room_type": {"type": "STRING", "description": "Single, Double, Twin, Deluxe, Family or Suite"},
            "check_in": {"type": "STRING", "description": "YYYY-MM-DD"},
            "check_out": {"type": "STRING", "description": "YYYY-MM-DD"},
            "guests": {"type": "INTEGER", "description": "number of guests"},
        },
        "required": ["room_type", "check_in", "check_out", "guests"],
    },
)

HOTEL_PHOTOS = types.FunctionDeclaration(
    name="hotel_photos",
    description="Photos of the hotel areas to show on the call screen.",
    behavior="NON_BLOCKING",
    parameters={
        "type": "OBJECT",
        "properties": {
            "area": {"type": "STRING", "description": "pool, spa, gym, restaurant, lobby or hotel"},
        },
    },
)

SEARCH_HOTEL_INFO = types.FunctionDeclaration(
    name="search_hotel_info",
    description="Search the hotel's information: policies, prices, opening hours, services, facilities, rooms and location, including distances to the airport and landmarks and what is near the hotel. Only for questions about Nile Pearl Hotel and a stay there; never search for unrelated topics such as sports, weather or politics, decline those yourself. Write the query yourself in English with the topic in it, never the guest's words as they are. If the guest asks several things, call it once for each question.",    behavior="NON_BLOCKING",
    parameters={
        "type": "OBJECT",
        "properties": {
            "question": {"type": "STRING", "description": "One clear English question with its topic, e.g. 'How to reach Gold level in the loyalty program?'"},
        },
        "required": ["question"],
    },
)

CREATE_REQUEST = types.FunctionDeclaration(
    name="create_request",
    description="Open a ticket for the hotel team: in-stay requests (housekeeping, room service, extra bed...), Maintenance for anything broken, Complaint, Special Request for a coming stay (needs a booking and a category), Discount Request, and Emergency for medical, fire or security (top priority, works without login). In an emergency, call this tool at once in the same turn, before or while you give the emergency numbers; never say the team was alerted unless this tool returned ok.",
    behavior="NON_BLOCKING",
    parameters={
        "type": "OBJECT",
        "properties": {
            "request_type": {"type": "STRING", "enum": list(REQUEST_TYPES)},
            "request_text": {"type": "STRING", "description": "What the guest needs, in one short English sentence."},
            "booking_ref": {"type": "STRING", "description": "B followed by six digits, only if the request is about a booking."},
            "category": {"type": "STRING", "enum": sorted({c for v in CATEGORIES.values() for c in v}), "description": "Only for a Complaint or a Special Request."},
        },
        "required": ["request_type", "request_text"],
    },
)

ESCALATE_TO_HUMAN = types.FunctionDeclaration(
    name="escalate_to_human",
    description="The guest has a problem and asked to talk to a person: hand the chat to a member of staff, or open an urgent callback ticket if no one is free.",
    behavior="NON_BLOCKING",
    parameters={
        "type": "OBJECT",
        "properties": {
            "reason": {"type": "STRING", "description": "The guest's problem in one short English sentence."},
            "booking_ref": {"type": "STRING", "description": "B followed by six digits, only if it is about a booking."},
        },
        "required": ["reason"],
    },
)

REF = {"type": "STRING", "description": "Booking reference: B followed by six digits, e.g. B013193"}
LAST_NAME = {"type": "STRING", "description": "Last name on the booking, only for a booking that is not in the caller's account"}
PHONE4 = {"type": "STRING", "description": "Last four digits of the phone on the booking, only for a booking that is not in the caller's account"}
DATE = {"type": "STRING", "description": "YYYY-MM-DD"}


def declare(name, description, properties=None, required=None):
    if not properties:
        return types.FunctionDeclaration(name=name, description=description, behavior="NON_BLOCKING")
    parameters = {"type": "OBJECT", "properties": properties}
    if required:
        parameters["required"] = required
    return types.FunctionDeclaration(name=name, description=description, behavior="NON_BLOCKING", parameters=parameters)


MY_BOOKINGS = declare(
    "my_bookings",
    "The logged-in caller's bookings (own and linked), newest first. Use it first when a logged-in caller talks about their booking; no further questions are needed for these.",
)

LINK_BOOKING = declare(
    "link_booking",
    "Add a booking made by phone, agency or a booking platform to the logged-in caller's account: the reference plus the last name or the last four phone digits.",
    {"booking_ref": REF, "last_name": LAST_NAME, "phone_last4": PHONE4},
    ["booking_ref"],
)

FIND_BOOKING = declare(
    "find_booking",
    "Details and payment status of one booking: free for a booking in the caller's account, otherwise only after the reference check (last name or last four phone digits).",
    {"booking_ref": REF, "last_name": LAST_NAME, "phone_last4": PHONE4},
    ["booking_ref"],
)

QUOTE_CANCELLATION = declare(
    "quote_cancellation",
    "What cancelling a booking would cost and refund now, by its rate plan. It does not cancel; tell the caller the cost before any cancellation.",
    {"booking_ref": REF, "last_name": LAST_NAME, "phone_last4": PHONE4},
    ["booking_ref"],
)

QUOTE_MODIFICATION = declare(
    "quote_modification",
    "New dates, room type or guests for a booking: availability, room and new total. It does not change the booking.",
    {
        "booking_ref": REF,
        "new_check_in": DATE,
        "new_check_out": DATE,
        "new_room_type": {"type": "STRING", "description": "Single, Double, Twin, Deluxe, Family or Suite"},
        "adults": {"type": "INTEGER"},
        "children": {"type": "INTEGER"},
        "last_name": LAST_NAME,
        "phone_last4": PHONE4,
    },
    ["booking_ref"],
)

LATE_CHECKOUT_QUOTE = declare(
    "late_checkout_quote",
    "Price of a late check-out for a booking until a given time, including the member benefit.",
    {
        "booking_ref": REF,
        "until": {"type": "STRING", "description": "HH:MM, e.g. 16:00"},
        "last_name": LAST_NAME,
        "phone_last4": PHONE4,
    },
    ["booking_ref", "until"],
)

CHECK_DISCOUNT_CODE = declare(
    "check_discount_code",
    "Whether a discount code is valid today and what it gives. A personal code works only for its own guest. Never say a code works without this tool.",
    {"code": {"type": "STRING", "description": "The code as the guest said it, e.g. PEARL100"}},
    ["code"],
)

LOYALTY_STATUS = declare(
    "loyalty_status",
    "Nile Pearl Rewards tier and points of the guest of a booking.",
    {"booking_ref": REF, "last_name": LAST_NAME, "phone_last4": PHONE4},
    ["booking_ref"],
)

MENU = declare(
    "menu",
    "The room-service menu with exact dish names, Arabic names, prices and dietary codes. Call it before room_service_quote to get the exact names.",
    {
        "night": {"type": "BOOLEAN", "description": "true for the night menu (11 PM to 6 AM)"},
        "category": {"type": "STRING", "enum": ["Starters", "Sandwiches", "Main courses", "Desserts", "Drinks", "Children"]},
    },
)

ROOM_SERVICE_QUOTE = declare(
    "room_service_quote",
    "Total of a room-service order including the 300 EGP delivery charge. It only prices the order; to place it, call create_request with request_type 'Room Service'.",
    {
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "item": {"type": "STRING", "description": "Exact dish name from the menu tool, e.g. Beef burger, Koshary, Mineral water, large"},
                    "qty": {"type": "INTEGER"},
                },
                "required": ["item", "qty"],
            },
        },
    },
    ["items"],
)

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")


def _token(account_id):
    url = os.getenv("DATABASE_URL", "").replace("+psycopg", "")
    with psycopg.connect(url) as db:
        row = db.execute(
            "SELECT role, customer_id, email_verified FROM user_accounts WHERE account_id = %s AND is_active",
            (int(account_id),),
        ).fetchone()
    if not row:
        return None
    now = datetime.now(timezone.utc)
    claims = {"sub": str(account_id), "role": row[0], "customer_id": row[1], "email_verified": row[2],
              "iat": now, "exp": now + timedelta(minutes=10)}
    return jwt.encode(claims, os.getenv("JWT_SECRET"), algorithm="HS256")


def _api(method, path, account_id, body=None):
    if not account_id:
        return {"ok": False, "reason": "NOT_LOGGED_IN", "advice": "ask the caller to log in on the website first"}
    try:
        token = _token(account_id)
    except psycopg.Error:
        return {"ok": False, "reason": "BOOKING_SYSTEM_DOWN", "advice": "ask the caller to call reception"}
    if not token:
        return {"ok": False, "reason": "UNKNOWN_ACCOUNT"}
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(API_URL + path, data=data, method=method,
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return {"ok": True, **json.loads(response.read())}
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read()).get("detail")
        except ValueError:
            detail = None
        if isinstance(detail, dict):
            return {"ok": False, "status": e.code, **detail}
        return {"ok": False, "status": e.code, "reason": str(detail or e.reason)}
    except urllib.error.URLError:
        return {"ok": False, "reason": "BOOKING_SYSTEM_DOWN", "advice": "ask the caller to call reception"}


def _cairo_time(result):
    if result.get("payment_due_at"):
        due = datetime.fromisoformat(result["payment_due_at"].replace("Z", "+00:00")).astimezone(ZoneInfo("Africa/Cairo"))
        result["pay_before"] = due.strftime("%d %B %Y, %H:%M") + " Cairo time"
        del result["payment_due_at"]
    return result


def make_booking(room_type, check_in, check_out, adults, children=0, rate_plan="Flexible",
                 discount_code=None, date_of_birth=None, account_id=None):
    body = {"room_type": room_type, "check_in": check_in, "check_out": check_out, "adults": int(adults),
            "children": int(children or 0), "rate_plan": rate_plan, "channel": "Voice Agent"}
    if discount_code:
        body["discount_code"] = discount_code
    if date_of_birth:
        body["date_of_birth"] = date_of_birth
    return _cairo_time(_api("POST", "/bookings", account_id, body))


def change_booking(booking_ref, new_check_in=None, new_check_out=None, new_room_type=None,
                   adults=None, children=None, account_id=None):
    body = {"check_in": new_check_in, "check_out": new_check_out, "room_type": new_room_type,
            "adults": None if adults is None else int(adults), "children": None if children is None else int(children)}
    body = {k: v for k, v in body.items() if v is not None}
    if not body:
        return {"ok": False, "reason": "NOTHING_TO_CHANGE"}
    return _cairo_time(_api("POST", f"/me/bookings/{booking_ref.strip().upper()}/change", account_id, body))


def cancel_booking(booking_ref, account_id=None):
    return _api("POST", f"/me/bookings/{booking_ref.strip().upper()}/cancel", account_id)


MAKE_BOOKING = declare(
    "make_booking",
    "Makes a new booking for the logged-in caller. Call it only after check_availability, after repeating room type, dates, guests, rate plan and total, and after the caller said yes. The booking is held as Pending until the amount pay_now is paid by payment_url before pay_before. If it returns DATE_OF_BIRTH_REQUIRED, ask the caller's date of birth and call it again with it.",
    {
        "room_type": {"type": "STRING", "description": "Single, Double, Twin, Deluxe, Family or Suite"},
        "check_in": DATE,
        "check_out": DATE,
        "adults": {"type": "INTEGER"},
        "children": {"type": "INTEGER"},
        "rate_plan": {"type": "STRING", "enum": ["Flexible", "Non-refundable"]},
        "discount_code": {"type": "STRING", "description": "Only if the caller gave a code that check_discount_code accepted"},
        "date_of_birth": DATE,
    },
    ["room_type", "check_in", "check_out", "adults"],
)

CHANGE_BOOKING = declare(
    "change_booking",
    "Changes dates, room type or guests of a booking in the caller's account. Call it only after quote_modification gave the new total and the caller said yes. Give only what changes.",
    {
        "booking_ref": REF,
        "new_check_in": DATE,
        "new_check_out": DATE,
        "new_room_type": {"type": "STRING", "description": "Single, Double, Twin, Deluxe, Family or Suite"},
        "adults": {"type": "INTEGER"},
        "children": {"type": "INTEGER"},
    },
    ["booking_ref"],
)

CANCEL_BOOKING = declare(
    "cancel_booking",
    "Cancels a booking in the caller's account for good. Call it only after quote_cancellation gave the charge and refund and the caller said yes to cancelling.",
    {"booking_ref": REF},
    ["booking_ref"],
)

DECLARATIONS = [
    CHECK_AVAILABILITY, HOTEL_PHOTOS, SEARCH_HOTEL_INFO, CREATE_REQUEST, ESCALATE_TO_HUMAN,
    MY_BOOKINGS, LINK_BOOKING, FIND_BOOKING, QUOTE_CANCELLATION, QUOTE_MODIFICATION,
    LATE_CHECKOUT_QUOTE, CHECK_DISCOUNT_CODE, LOYALTY_STATUS, MENU, ROOM_SERVICE_QUOTE,
    MAKE_BOOKING, CHANGE_BOOKING, CANCEL_BOOKING,
]
FUNCTIONS = {
    "check_availability": check_availability,
    "hotel_photos": hotel_photos,
    "search_hotel_info": search_hotel_info,
    "create_request": create_request,
    "escalate_to_human": escalate_to_human,
    "my_bookings": my_bookings,
    "link_booking": link_booking,
    "find_booking": find_booking,
    "quote_cancellation": quote_cancellation,
    "quote_modification": quote_modification,
    "late_checkout_quote": late_checkout_quote,
    "check_discount_code": check_discount_code,
    "loyalty_status": loyalty_status,
    "menu": menu,
    "room_service_quote": room_service_quote,
    "make_booking": make_booking,
    "change_booking": change_booking,
    "cancel_booking": cancel_booking,
}
