import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.config import settings
from app.api.db import engine
from app.api.services.bookings import HOTEL_NOW
from app.api.services.email import notify

logger = logging.getLogger("hotel_api")

# queries.sql 4c, on the hotel clock: a Pending booking whose payment link was not paid in time is cancelled,
# its payment row becomes Expired, the room is free again and a discount code it used is given back.
# All three changes are one statement, so they happen together or not at all.
EXPIRE_SQL = text(f"""
    WITH expired AS (
        UPDATE payments p SET payment_status = 'Expired'
        FROM bookings b
        WHERE b.booking_id = p.booking_id
          AND b.booking_status = 'Pending' AND p.payment_status = 'Pending'
          AND p.payment_due_at < {HOTEL_NOW}
          AND (CAST(:only AS text[]) IS NULL OR b.booking_id = ANY(CAST(:only AS text[])))
        RETURNING p.booking_id
    ), cancelled AS (
        UPDATE bookings SET booking_status = 'Cancelled', cancelled_at = now()
        WHERE booking_id IN (SELECT booking_id FROM expired)
        RETURNING booking_id, discount_code_id
    ), codes_back AS (
        UPDATE discount_codes d
        SET usage_count = d.usage_count - c.uses,
            status = CASE WHEN d.status = 'Exhausted' THEN 'Active' ELSE d.status END
        FROM (SELECT discount_code_id, count(*) AS uses FROM cancelled
              WHERE discount_code_id IS NOT NULL GROUP BY discount_code_id) c
        WHERE d.code_id = c.discount_code_id
    )
    SELECT booking_id FROM cancelled ORDER BY booking_id
""")


async def expire_unpaid_bookings(db: AsyncConnection, only: list[str] | None = None) -> list[str]:
    """Cancels the bookings whose payment hold is over. `only` limits it to some bookings (used by the tests)."""
    cancelled = (await db.execute(EXPIRE_SQL, {"only": only})).scalars().all()
    await db.commit()
    for booking_id in cancelled:
        logger.info("Booking %s cancelled: its payment link was not paid in time", booking_id)
        await notify(booking_id, "expired", db)
    return list(cancelled)


async def expiry_job() -> None:
    """Runs in the background while the API is up, every EXPIRY_CHECK_SECONDS."""
    while True:
        try:
            async with engine.connect() as db:
                await expire_unpaid_bookings(db)
        except Exception:
            # one failed round (e.g. the database restarting) must not stop the job
            logger.exception("Expiry job failed, will try again")
        await asyncio.sleep(settings.expiry_check_seconds)
