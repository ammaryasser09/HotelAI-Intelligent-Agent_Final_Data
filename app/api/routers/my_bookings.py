from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.config import settings
from app.api.db import get_db
from app.api.rate_limit import limiter
from app.api.schemas.auth import CurrentAccount
from app.api.schemas.bookings import BookingSummary, LinkBookingRequest
from app.api.security import get_current_guest

router = APIRouter(tags=["My bookings"])

# queries.sql 2: the bookings of the account (its own + the linked ones); one booking when booking_ref is given
ACCOUNT_BOOKINGS_SQL = text("""
    SELECT d.booking_id, ab.access, d.booking_status, d.rate_plan, d.check_in, d.check_out, d.nights,
           d.adults, d.children, d.room_type_name, d.room_number, d.view, d.price_per_night,
           d.total_amount, d.discount_source, d.discount_amount, d.amount_due,
           d.payment_status, d.amount_paid, d.refund_amount, d.payment_due_at
    FROM v_account_bookings ab
    JOIN v_booking_details d USING (booking_id)
    WHERE ab.account_id = :account_id
      AND (CAST(:booking_ref AS text) IS NULL OR d.booking_id = upper(CAST(:booking_ref AS text)))
    ORDER BY d.check_in DESC
""")

# queries.sql 2b: the reference AND (last name in English or Arabic, or the last 4 phone digits) must match
VERIFY_BOOKING_SQL = text("""
    SELECT booking_id
    FROM v_booking_details
    WHERE booking_id = upper(:booking_ref)
      AND (lower(last_name) = lower(CAST(:last_name AS text))
           OR last_name_ar = CAST(:last_name AS text)
           OR phone_last4 = CAST(:phone_last4 AS text))
""")
LINK_SQL = text("""
    INSERT INTO booking_links (account_id, booking_id) VALUES (:account_id, upper(:booking_ref))
    ON CONFLICT DO NOTHING
""")


async def account_bookings(db: AsyncConnection, account_id: int, booking_ref: str | None = None):
    rows = (await db.execute(
        ACCOUNT_BOOKINGS_SQL, {"account_id": account_id, "booking_ref": booking_ref}
    )).mappings().all()
    return [BookingSummary(**row) for row in rows]


@router.get("/me/bookings", response_model=list[BookingSummary])
async def my_bookings(guest: CurrentAccount = Depends(get_current_guest), db: AsyncConnection = Depends(get_db)):
    return await account_bookings(db, guest.account_id)


@router.post("/me/bookings/link", response_model=BookingSummary)
@limiter.limit(settings.link_rate_limit)
async def link_booking(
    request: Request,
    body: LinkBookingRequest,
    guest: CurrentAccount = Depends(get_current_guest),
    db: AsyncConnection = Depends(get_db),
):
    already = await account_bookings(db, guest.account_id, body.booking_ref)
    if already:
        return already[0]

    verified = (await db.execute(VERIFY_BOOKING_SQL, {
        "booking_ref": body.booking_ref,
        "last_name": body.last_name.strip() if body.last_name else None,
        "phone_last4": body.phone_last4,
    })).first()
    if verified is None:
        # One answer for "no such booking" and "wrong name": references cannot be guessed
        raise HTTPException(status_code=404, detail={"reason": "BOOKING_NOT_FOUND_OR_NOT_VERIFIED"})

    await db.execute(LINK_SQL, {"account_id": guest.account_id, "booking_ref": body.booking_ref})
    await db.commit()
    return (await account_bookings(db, guest.account_id, body.booking_ref))[0]
