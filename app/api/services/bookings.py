from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

# The hotel clock: today's date from app_settings (frozen while the demo data is in use) at the current time.
# Payment holds are set and checked on this clock, so the demo bookings and new ones follow the same rules.
HOTEL_NOW = "(hotel_today() + localtime)"

# What is still to be paid for a booking, and by when
PAYMENT_STATE_SQL = text(f"""
    SELECT b.booking_id, b.booking_status, b.rate_plan, b.price_per_night, b.nights, b.amount_due,
           p.payment_status, p.payment_due_at, (p.payment_due_at < {HOTEL_NOW}) AS overdue,
           (SELECT value::int FROM app_settings WHERE key = 'deposit_nights') AS deposit_nights
    FROM bookings b
    JOIN payments p USING (booking_id)
    WHERE b.booking_id = upper(:booking_ref)
""")

# queries.sql 4b: the payment gateway reports the link as paid
PAID_SQL = text("""
    UPDATE payments SET payment_status = 'Paid', amount_paid = :amount
    WHERE booking_id = upper(:booking_ref) AND payment_status = 'Pending'
""")
CONFIRM_SQL = text("""
    UPDATE bookings SET booking_status = 'Confirmed'
    WHERE booking_id = upper(:booking_ref) AND booking_status = 'Pending'
""")


def amount_to_pay_now(state) -> Decimal:
    """Flexible: the deposit (deposit_nights nights). Non-refundable: everything."""
    if state["rate_plan"] == "Non-refundable":
        return state["amount_due"]
    deposit = state["price_per_night"] * min(state["nights"], state["deposit_nights"] or 1)
    return min(deposit, state["amount_due"])


async def payment_state(db: AsyncConnection, booking_ref: str):
    return (await db.execute(PAYMENT_STATE_SQL, {"booking_ref": booking_ref})).mappings().first()


async def confirm_payment(db: AsyncConnection, booking_ref: str, amount: Decimal) -> None:
    """Payment received: the payment becomes Paid and the booking Confirmed, both or neither."""
    await db.execute(PAID_SQL, {"booking_ref": booking_ref, "amount": amount})
    await db.execute(CONFIRM_SQL, {"booking_ref": booking_ref})
    await db.commit()
