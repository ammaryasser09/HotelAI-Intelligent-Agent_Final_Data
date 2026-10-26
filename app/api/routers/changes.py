from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.config import settings
from app.api.db import get_db
from app.api.routers.availability import HOTEL_RULES_SQL, ROOM_TYPE_SQL
from app.api.routers.bookings import GUEST_CONTACT_SQL, ROOM_TRIES
from app.api.routers.cancellations import CODE_BACK_SQL, REFUND_SQL
from app.api.schemas.auth import CurrentAccount
from app.api.schemas.bookings import BookingChange, ChangeBookingRequest
from app.api.schemas.discounts import DiscountCodeCheck
from app.api.security import get_current_guest
from app.api.services.email import notify
from app.api.services.payments import PaymentProviderError, create_payment_link, refund_payment
from app.api.services.pricing import money, price_stay

router = APIRouter(tags=["My bookings"])

BOOKING_TO_CHANGE_SQL = """
    SELECT b.booking_id, b.booking_status, b.booking_channel, b.rate_plan, b.room_type_id, b.room_number,
           b.check_in, b.check_out, b.adults, b.children, b.price_per_night, b.discount_code_id,
           c.discount_code, c.discount_type, c.discount_value,
           p.payment_status, p.amount_paid, p.refund_amount, p.transaction_reference,
           b.check_in > hotel_today() AS before_arrival_day
    FROM bookings b
    JOIN payments p USING (booking_id)
    LEFT JOIN discount_codes c ON c.code_id = b.discount_code_id
    WHERE b.booking_id = upper(:booking_ref)
      AND EXISTS (SELECT 1 FROM v_account_bookings ab
                  WHERE ab.account_id = :account_id AND ab.booking_id = b.booking_id)
"""
READ_SQL = text(BOOKING_TO_CHANGE_SQL)
LOCK_SQL = text(BOOKING_TO_CHANGE_SQL + " FOR UPDATE OF b, p")

# queries.sql 9a: a free room for the new stay, not counting this booking itself (same room first, then Nile view)
FIND_ROOM_SQL = text("""
    SELECT r.room_number, r.view FROM rooms r
    WHERE r.room_type_id = :room_type_id AND r.status <> 'Maintenance'
      AND NOT EXISTS (SELECT 1 FROM bookings b
                      WHERE b.room_number = r.room_number AND b.booking_id <> :booking_id
                        AND b.booking_status IN ('Pending', 'Confirmed', 'Completed')
                        AND b.check_in < :check_out AND :check_in < b.check_out)
    ORDER BY (r.room_number = :current_room) DESC, (r.view = 'Nile') DESC, r.room_number
    LIMIT 1
""")

# queries.sql 9b (+ the discount, worked out again for the new stay)
CHANGE_SQL = text("""
    UPDATE bookings
    SET check_in = :check_in, check_out = :check_out, room_type_id = :room_type_id, room_number = :room_number,
        adults = :adults, children = :children, price_per_night = :price_per_night,
        discount_source = :discount_source, discount_code_id = :discount_code_id, discount_amount = :discount_amount
    WHERE booking_id = :booking_id AND booking_status IN ('Pending', 'Confirmed') AND rate_plan = 'Flexible'
    RETURNING nights, total_amount, amount_due
""")


def refuse(status: int, reason: str, **extra) -> HTTPException:
    return HTTPException(status_code=status, detail={"reason": reason, **extra})


async def load(db: AsyncConnection, sql, booking_id: str, account_id: int):
    booking = (await db.execute(sql, {"booking_ref": booking_id, "account_id": account_id})).mappings().first()
    if booking is None:
        raise refuse(404, "BOOKING_NOT_FOUND")
    if booking["booking_status"] not in ("Pending", "Confirmed"):
        raise refuse(409, "NOT_CHANGEABLE", booking_status=booking["booking_status"])
    if not booking["before_arrival_day"]:
        raise refuse(409, "TOO_LATE_TO_CHANGE")                 # from the arrival day on: the front desk
    if booking["rate_plan"] != "Flexible":
        raise refuse(409, "NON_REFUNDABLE_CANNOT_CHANGE")
    if booking["booking_channel"] == "Booking Platform":
        raise refuse(409, "CHANGE_ON_BOOKING_PLATFORM")         # Booking.com bookings are changed there
    return booking


async def plan(db: AsyncConnection, booking, change: ChangeBookingRequest) -> dict:
    """Works out the booking after the change. Reads only; nothing is saved here."""
    room_type = (await db.execute(ROOM_TYPE_SQL, {"room_type": change.room_type or booking["room_type_id"]})).mappings().first()
    if room_type is None:
        raise refuse(404, "UNKNOWN_ROOM_TYPE")
    rules = (await db.execute(HOTEL_RULES_SQL)).mappings().one()

    new = {
        "check_in": change.check_in or booking["check_in"],
        "check_out": change.check_out or booking["check_out"],
        "adults": booking["adults"] if change.adults is None else change.adults,
        "children": booking["children"] if change.children is None else change.children,
        "room_type_id": room_type["room_type_id"],
    }
    if all(new[key] == booking[key] for key in new):
        raise refuse(400, "NOTHING_TO_CHANGE")
    if new["check_out"] <= new["check_in"]:
        raise refuse(400, "CHECK_OUT_NOT_AFTER_CHECK_IN")
    if new["check_in"] < rules["today"]:
        raise refuse(400, "CHECK_IN_IN_THE_PAST", today=str(rules["today"]))
    if new["adults"] + new["children"] > room_type["capacity"]:
        raise refuse(400, "CAPACITY_EXCEEDED", capacity=room_type["capacity"])

    # New dates keep the agreed nightly price; another room type is priced at its own base price.
    same_type = room_type["room_type_id"] == booking["room_type_id"]
    price_per_night = booking["price_per_night"] if same_type else room_type["base_price"]
    nights = (new["check_out"] - new["check_in"]).days
    code = None
    if booking["discount_code_id"]:   # the code the guest already used, worked out again on the new total
        code = DiscountCodeCheck(code=booking["discount_code"], usable=True, discount_type=booking["discount_type"],
                                 discount_value=float(booking["discount_value"]), code_id=booking["discount_code_id"])
    flexible, _ = price_stay(
        rate_per_night=price_per_night,
        nights=nights,
        long_stay_multiplier=rules["long_stay_multiplier"],
        long_stay_min_nights=settings.long_stay_min_nights,
        deposit_nights=rules["deposit_nights"] or 1,
        non_refundable_multiplier=settings.non_refundable_multiplier,
        code=code,
    )
    discount = flexible.discount
    amount_due = Decimal(str(flexible.amount_due))

    held = booking["amount_paid"] - booking["refund_amount"]
    refund = max(held - amount_due, Decimal(0))      # got cheaper than what was already paid
    pay_now = Decimal(str(flexible.deposit_now)) if booking["payment_status"] == "Pending" else Decimal(0)

    return {
        **new,
        "room_type_name": room_type["room_type_name"],
        "nights": nights,
        "price_per_night": price_per_night,
        "discount": discount,
        "discount_source": discount.source if discount else None,
        "discount_code_id": booking["discount_code_id"] if discount and discount.source == "Code" else None,
        "discount_amount": Decimal(str(discount.amount)) if discount else Decimal(0),
        "amount_due": amount_due,
        "held_after": held - refund,
        "refund": refund,
        "pay_now": pay_now,
    }


async def free_room(db: AsyncConnection, booking, new: dict):
    room = (await db.execute(FIND_ROOM_SQL, {
        "room_type_id": new["room_type_id"], "booking_id": booking["booking_id"], "current_room": booking["room_number"],
        "check_in": new["check_in"], "check_out": new["check_out"],
    })).mappings().first()
    if room is None:
        raise refuse(409, "NO_ROOM_AVAILABLE")
    return room


def result(booking, new: dict, room, payment_url: str | None = None) -> BookingChange:
    pay_at_hotel = new["amount_due"] - new["held_after"] - new["pay_now"]
    return BookingChange(
        booking_id=booking["booking_id"], booking_status=booking["booking_status"],
        room_type=new["room_type_name"], room_number=room["room_number"], view=room["view"],
        check_in=new["check_in"], check_out=new["check_out"], nights=new["nights"],
        adults=new["adults"], children=new["children"],
        price_per_night=money(new["price_per_night"]),
        total_amount=money(new["price_per_night"] * new["nights"]),
        discount=new["discount"], amount_due=money(new["amount_due"]),
        amount_paid=money(new["held_after"]), pay_now=money(new["pay_now"]),
        pay_at_hotel=money(max(pay_at_hotel, Decimal(0))), refund=money(new["refund"]),
        payment_url=payment_url,
    )


@router.get("/me/bookings/{booking_id}/change", response_model=BookingChange)
async def change_quote(
    booking_id: str,
    change: Annotated[ChangeBookingRequest, Query()],
    guest: CurrentAccount = Depends(get_current_guest),
    db: AsyncConnection = Depends(get_db),
):
    """What the booking would look like and cost after the change. Nothing is saved."""
    booking = await load(db, READ_SQL, booking_id, guest.account_id)
    new = await plan(db, booking, change)
    return result(booking, new, await free_room(db, booking, new))


@router.post("/me/bookings/{booking_id}/change", response_model=BookingChange)
async def change_booking(
    request: Request,
    booking_id: str,
    change: ChangeBookingRequest,
    background: BackgroundTasks,
    guest: CurrentAccount = Depends(get_current_guest),
    db: AsyncConnection = Depends(get_db),
):
    """Applies the change in one transaction, on the same terms as the quote."""
    booking = await load(db, LOCK_SQL, booking_id, guest.account_id)
    new = await plan(db, booking, change)

    # 1. the booking itself: another guest may take the free room in the same moment, then the next one is tried
    room = None
    for _ in range(ROOM_TRIES):
        room = await free_room(db, booking, new)
        try:
            async with db.begin_nested():
                await db.execute(CHANGE_SQL, {key: new[key] for key in (
                    "check_in", "check_out", "room_type_id", "adults", "children", "price_per_night",
                    "discount_source", "discount_code_id", "discount_amount")} | {
                    "booking_id": booking["booking_id"], "room_number": room["room_number"]})
            break
        except IntegrityError as error:
            if "no_double_booking" not in str(error):
                raise
            room = None
    if room is None:
        raise refuse(409, "ROOM_JUST_TAKEN")

    # 2. a code the new stay no longer uses (the Long Stay discount is now bigger) can be used again
    if booking["discount_code_id"] and new["discount_code_id"] is None:
        await db.execute(CODE_BACK_SQL, {"code_id": booking["discount_code_id"]})

    # 3. money: a cheaper stay than what was paid gets the difference back; a Pending booking gets a new link
    payment_url = None
    try:
        if new["refund"] > 0:
            await refund_payment(booking["booking_id"], new["refund"], booking["transaction_reference"])
            await db.execute(REFUND_SQL, {"booking_id": booking["booking_id"], "refund": new["refund"]})
        if booking["payment_status"] == "Pending":
            contact = (await db.execute(GUEST_CONTACT_SQL, {"customer_id": guest.customer_id})).mappings().one()
            payment_url = await create_payment_link(request, booking["booking_id"], new["pay_now"], contact)
    except PaymentProviderError:
        await db.rollback()
        raise refuse(502, "PAYMENT_PROVIDER_ERROR")

    await db.commit()
    background.add_task(notify, booking["booking_id"], "changed")
    return result(booking, new, room, payment_url)
