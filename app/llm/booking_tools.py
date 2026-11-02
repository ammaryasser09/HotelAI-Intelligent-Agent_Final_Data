from google.genai import types
from app.rag.tools import (
    my_bookings, link_booking, find_booking, quote_cancellation, quote_modification,
    late_checkout_quote, check_discount_code, loyalty_status, menu, room_service_quote,
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

BOOKING_DECLARATIONS = [
    MY_BOOKINGS, LINK_BOOKING, FIND_BOOKING, QUOTE_CANCELLATION, QUOTE_MODIFICATION,
    LATE_CHECKOUT_QUOTE, CHECK_DISCOUNT_CODE, LOYALTY_STATUS, MENU, ROOM_SERVICE_QUOTE,
]
BOOKING_FUNCTIONS = {
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
}
