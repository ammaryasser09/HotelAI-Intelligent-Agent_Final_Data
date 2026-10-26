from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.config import settings
from app.api.db import get_db
from app.api.routers.availability import FREE_ROOMS_SQL, HOTEL_RULES_SQL, ROOM_TYPE_SQL
from app.api.schemas.auth import CurrentAccount
from app.api.schemas.bookings import BookingCreated, CreateBookingRequest
from app.api.security import get_current_guest
from app.api.services.discounts import check_code
from app.api.services.payments import create_payment_link
from app.api.services.pricing import CENT, money, price_stay

router = APIRouter(tags=["Bookings"])

# queries.sql 4: the new booking waits for its payment as Pending (the room is held meanwhile)
INSERT_BOOKING_SQL = text("""
    INSERT INTO bookings (customer_id, room_number, room_type_id, check_in, check_out, adults, children,
                          booking_status, booking_channel, rate_plan, price_per_night,
                          discount_source, discount_code_id, discount_amount, created_at)
    VALUES (:customer_id, :room_number, :room_type_id, :check_in, :check_out, :adults, :children,
            'Pending', :channel, :rate_plan, :price_per_night,
            :discount_source, :discount_code_id, :discount_amount, now())
    RETURNING booking_id, nights, total_amount, discount_amount, amount_due
""")

# queries.sql 4: a code was used, count it (a personal code becomes Exhausted after its one use)
USE_CODE_SQL = text("""
    UPDATE discount_codes SET usage_count = usage_count + 1,
           status = CASE WHEN max_usage IS NOT NULL AND usage_count + 1 >= max_usage THEN 'Exhausted' ELSE status END
    WHERE code_id = :code_id
""")

# queries.sql 4: the payment row. Held 24 h, or 2 h when arrival (3 PM) is less than 24 h away on the hotel clock
INSERT_PAYMENT_SQL = text("""
    INSERT INTO payments (booking_id, payment_method, payment_status, payment_due_at, created_at)
    VALUES (:booking_id, :payment_method, 'Pending',
            now() + make_interval(hours => CASE
                WHEN (CAST(:check_in AS date) + time '15:00') - (hotel_today() + localtime) < interval '24 hours'
                THEN (SELECT value::int FROM app_settings WHERE key = 'deposit_hold_hours_last_minute')
                ELSE (SELECT value::int FROM app_settings WHERE key = 'deposit_hold_hours') END),
            now())
    RETURNING payment_due_at
""")

ROOM_TRIES = 3  # if another guest takes the chosen room in the same moment, try the next free one


def refuse(status: int, reason: str, **extra) -> HTTPException:
    return HTTPException(status_code=status, detail={"reason": reason, **extra})


@router.post("/bookings", response_model=BookingCreated, status_code=201)
async def create_booking(
    request: Request,
    body: CreateBookingRequest,
    guest: CurrentAccount = Depends(get_current_guest),
    db: AsyncConnection = Depends(get_db),
):
    # 1. the same checks as /availability
    room_type = (await db.execute(ROOM_TYPE_SQL, {"room_type": body.room_type})).mappings().first()
    if room_type is None:
        raise refuse(404, "UNKNOWN_ROOM_TYPE")
    rules = (await db.execute(HOTEL_RULES_SQL)).mappings().one()
    if body.check_in < rules["today"]:
        raise refuse(400, "CHECK_IN_IN_THE_PAST", today=str(rules["today"]))
    if body.guests > room_type["capacity"]:
        raise refuse(400, "CAPACITY_EXCEEDED", capacity=room_type["capacity"])

    # 2. the price: one discount at most, and only on the Flexible rate
    base = room_type["base_price"]
    code, code_not_used = None, None
    if body.discount_code and body.rate_plan == "Non-refundable":
        code_not_used = "NOT_ON_NON_REFUNDABLE"
    elif body.discount_code:
        code = await check_code(db, body.discount_code, customer_id=guest.customer_id)
        if code is None:
            code_not_used = "CODE_NOT_FOUND"
        elif not code.usable:
            code_not_used = code.reason

    flexible, non_refundable = price_stay(
        rate_per_night=base,
        nights=body.nights,
        long_stay_multiplier=rules["long_stay_multiplier"],
        long_stay_min_nights=settings.long_stay_min_nights,
        deposit_nights=rules["deposit_nights"] or 1,
        non_refundable_multiplier=settings.non_refundable_multiplier,
        code=code,
    )
    if body.rate_plan == "Flexible":
        price_per_night, discount = base, flexible.discount
        if code is not None and code.usable and (discount is None or discount.source != "Code"):
            code_not_used = "LONG_STAY_DISCOUNT_IS_BIGGER"
    else:
        price_per_night, discount = (base * settings.non_refundable_multiplier).quantize(CENT), None

    values = {
        "customer_id": guest.customer_id,
        "room_type_id": room_type["room_type_id"],
        "check_in": body.check_in,
        "check_out": body.check_out,
        "adults": body.adults,
        "children": body.children,
        "channel": body.channel,
        "rate_plan": body.rate_plan,
        "price_per_night": price_per_night,
        "discount_source": discount.source if discount else None,
        "discount_code_id": code.code_id if discount and discount.source == "Code" else None,
        "discount_amount": Decimal(str(discount.amount)) if discount else Decimal(0),
    }

    # 3. take a free room (Nile view first). The database refuses a room taken a moment ago
    #    (constraint no_double_booking), so the next free room is tried.
    booking, room = None, None
    for _ in range(ROOM_TRIES):
        free = (await db.execute(FREE_ROOMS_SQL, {
            "room_type": room_type["room_type_id"], "check_in": body.check_in, "check_out": body.check_out,
        })).mappings().all()
        if not free:
            raise refuse(409, "NO_ROOM_AVAILABLE")
        room = free[0]
        try:
            async with db.begin_nested():  # a savepoint: a refused insert does not undo the rest
                booking = (await db.execute(
                    INSERT_BOOKING_SQL, {**values, "room_number": room["room_number"]}
                )).mappings().one()
            break
        except IntegrityError as error:
            if "no_double_booking" not in str(error):
                raise
    if booking is None:
        raise refuse(409, "ROOM_JUST_TAKEN")

    # 4. count the code, open the payment, make the link; one transaction for all of it
    if values["discount_code_id"]:
        await db.execute(USE_CODE_SQL, {"code_id": values["discount_code_id"]})
    payment_due_at = (await db.execute(INSERT_PAYMENT_SQL, {
        "booking_id": booking["booking_id"], "payment_method": body.payment_method, "check_in": body.check_in,
    })).scalar_one()

    amount_due = booking["amount_due"]
    if body.rate_plan == "Flexible":
        pay_now = min(price_per_night * min(body.nights, rules["deposit_nights"] or 1), amount_due)
    else:
        pay_now = amount_due
    payment_url = await create_payment_link(request, booking["booking_id"], pay_now)
    await db.commit()

    return BookingCreated(
        booking_id=booking["booking_id"],
        booking_status="Pending",
        room_type=room_type["room_type_name"],
        room_number=room["room_number"],
        view=room["view"],
        check_in=body.check_in,
        check_out=body.check_out,
        nights=booking["nights"],
        adults=body.adults,
        children=body.children,
        rate_plan=body.rate_plan,
        price_per_night=money(price_per_night),
        total_amount=money(booking["total_amount"]),
        discount=discount,
        amount_due=money(amount_due),
        pay_now=money(pay_now),
        pay_at_hotel=money(amount_due - pay_now),
        payment_due_at=payment_due_at,
        payment_url=payment_url,
        discount_code_not_used=code_not_used,
    )
