from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.db import get_db
from app.api.schemas.auth import CurrentAccount
from app.api.schemas.bookings import CancellationQuote, CancellationResult
from app.api.security import get_current_guest
from app.api.services.bookings import HOTEL_NOW
from app.api.services.payments import PaymentProviderError, refund_payment
from app.api.services.pricing import money

router = APIRouter(tags=["My bookings"])

# queries.sql 3: one booking of this account (its own or a linked one) with what is needed to price a cancellation.
# Free for the Flexible rate until free_cancellation_hours (48) before 3 PM on the arrival day.
BOOKING_TO_CANCEL_SQL = f"""
    SELECT b.booking_id, b.booking_status, b.rate_plan, b.check_in, b.price_per_night, b.amount_due,
           b.discount_code_id, p.payment_status, p.amount_paid, p.refund_amount, p.transaction_reference,
           (b.check_in + time '15:00') - make_interval(hours => (
               SELECT value::int FROM app_settings WHERE key = 'free_cancellation_hours')) AS free_until,
           {HOTEL_NOW} AS hotel_now,
           b.check_in > hotel_today() AS before_arrival_day
    FROM bookings b
    JOIN payments p USING (booking_id)
    WHERE b.booking_id = upper(:booking_ref)
      AND EXISTS (SELECT 1 FROM v_account_bookings ab
                  WHERE ab.account_id = :account_id AND ab.booking_id = b.booking_id)
"""
QUOTE_SQL = text(BOOKING_TO_CANCEL_SQL)
# the same row, locked until commit: a payment or the expiry job arriving at the same moment waits for us
LOCK_SQL = text(BOOKING_TO_CANCEL_SQL + " FOR UPDATE OF b, p")

# queries.sql 3b
CANCEL_SQL = text("""
    UPDATE bookings SET booking_status = 'Cancelled', cancelled_at = now()
    WHERE booking_id = :booking_id AND booking_status IN ('Pending', 'Confirmed')
""")
REFUND_SQL = text("""
    UPDATE payments
    SET refund_amount = refund_amount + CAST(:refund AS numeric),
        payment_status = CASE
            WHEN payment_status = 'Pending' THEN 'Expired'         -- the link was never paid: it is closed
            WHEN CAST(:refund AS numeric) = 0 THEN payment_status
            WHEN refund_amount + CAST(:refund AS numeric) = amount_paid THEN 'Refunded'
            ELSE 'Partially Refunded' END
    WHERE booking_id = :booking_id
    RETURNING payment_status
""")
# the guest did not get the stay, so a discount code used on it can be used again
CODE_BACK_SQL = text("""
    UPDATE discount_codes
    SET usage_count = usage_count - 1,
        status = CASE WHEN status = 'Exhausted' THEN 'Active' ELSE status END
    WHERE code_id = :code_id AND usage_count > 0
""")


def terms(booking) -> tuple[bool, Decimal, Decimal]:
    """(is_free, charge, refund). The hotel never keeps more than it was paid."""
    is_free = booking["rate_plan"] == "Flexible" and booking["hotel_now"] < booking["free_until"]
    if booking["rate_plan"] == "Non-refundable":
        charge = booking["amount_due"]
    elif is_free:
        charge = Decimal("0")
    else:
        charge = booking["price_per_night"]          # the first night (the deposit) is kept
    held = booking["amount_paid"] - booking["refund_amount"]
    kept = min(charge, held)
    return is_free, kept, held - kept


def check_cancellable(booking) -> None:
    if booking is None:
        raise HTTPException(status_code=404, detail={"reason": "BOOKING_NOT_FOUND"})
    if booking["booking_status"] not in ("Pending", "Confirmed"):
        raise HTTPException(status_code=409, detail={"reason": "NOT_CANCELLABLE",
                                                     "booking_status": booking["booking_status"]})
    if not booking["before_arrival_day"]:
        # from the arrival day on, the front desk handles it (check-in, no-show)
        raise HTTPException(status_code=409, detail={"reason": "TOO_LATE_TO_CANCEL"})


@router.get("/me/bookings/{booking_id}/cancellation", response_model=CancellationQuote)
async def cancellation_quote(
    booking_id: str,
    guest: CurrentAccount = Depends(get_current_guest),
    db: AsyncConnection = Depends(get_db),
):
    booking = (await db.execute(QUOTE_SQL, {"booking_ref": booking_id, "account_id": guest.account_id})).mappings().first()
    check_cancellable(booking)
    is_free, charge, refund = terms(booking)
    return CancellationQuote(
        booking_id=booking["booking_id"],
        booking_status=booking["booking_status"],
        rate_plan=booking["rate_plan"],
        check_in=booking["check_in"],
        free_cancellation_until=booking["free_until"] if booking["rate_plan"] == "Flexible" else None,
        is_free=is_free,
        amount_paid=money(booking["amount_paid"] - booking["refund_amount"]),
        charge=money(charge),
        refund=money(refund),
    )


@router.post("/me/bookings/{booking_id}/cancel", response_model=CancellationResult)
async def cancel_booking(
    booking_id: str,
    guest: CurrentAccount = Depends(get_current_guest),
    db: AsyncConnection = Depends(get_db),
):
    """Cancels for good, on the same terms the quote shows. One transaction; the card refund is sent before
    anything is saved, so if Paymob refuses it the booking stays as it was."""
    booking = (await db.execute(LOCK_SQL, {"booking_ref": booking_id, "account_id": guest.account_id})).mappings().first()
    check_cancellable(booking)
    _, charge, refund = terms(booking)

    try:
        await refund_payment(booking["booking_id"], refund, booking["transaction_reference"])
    except PaymentProviderError:
        await db.rollback()
        raise HTTPException(status_code=502, detail={"reason": "REFUND_FAILED"})

    await db.execute(CANCEL_SQL, {"booking_id": booking["booking_id"]})
    payment_status = (await db.execute(REFUND_SQL, {"booking_id": booking["booking_id"], "refund": refund})).scalar_one()
    if booking["discount_code_id"]:
        await db.execute(CODE_BACK_SQL, {"code_id": booking["discount_code_id"]})
    await db.commit()

    return CancellationResult(booking_id=booking["booking_id"], booking_status="Cancelled",
                              payment_status=payment_status, charge=money(charge), refund=money(refund))
