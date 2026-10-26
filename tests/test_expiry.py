import asyncio

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.config import settings
from app.api.services.expiry import expire_unpaid_bookings
from tests.test_auth import bearer
from tests.test_bookings import STAY, book, database, made, token  # noqa: F401  (pytest fixtures)


def run_expiry(booking_id):
    """Runs the job once, only on this booking, so the demo bookings are never touched by the tests."""
    async def once():
        engine = create_async_engine(make_url(settings.database_url).set(drivername="postgresql+asyncpg"))
        async with engine.connect() as db:
            cancelled = await expire_unpaid_bookings(db, only=[booking_id])
        await engine.dispose()
        return cancelled
    return asyncio.run(once())


def hold_is_over(booking_id):
    """Moves the payment deadline one minute into the past on the hotel clock."""
    engine = database()
    with engine.begin() as connection:
        connection.execute(text("""
            UPDATE payments SET payment_due_at = hotel_today() + localtime - interval '1 minute'
            WHERE booking_id = :b"""), {"b": booking_id})
    engine.dispose()


def code_uses(code):
    engine = database()
    with engine.connect() as connection:
        uses = connection.execute(text("SELECT usage_count FROM discount_codes WHERE discount_code = :c"),
                                  {"c": code}).scalar_one()
    engine.dispose()
    return uses


def status_of(client, token, booking_id):
    mine = {b["booking_id"]: b for b in client.get("/me/bookings", headers=bearer(token)).json()}
    return mine[booking_id]["booking_status"], mine[booking_id]["payment_status"]


def test_booking_still_in_its_hold_is_left_alone(client, token, made):
    booking_id = book(client, token, made).json()["booking_id"]
    assert run_expiry(booking_id) == []
    assert status_of(client, token, booking_id) == ("Pending", "Pending")


def test_unpaid_booking_is_cancelled_and_its_room_freed(client, token, made):
    booking = book(client, token, made).json()
    hold_is_over(booking["booking_id"])

    # the guest is too late to pay now
    late = client.post(f"/payments/mock/{booking['booking_id']}/pay")
    assert late.status_code == 409 and late.json()["detail"]["reason"] == "PAYMENT_EXPIRED"

    assert run_expiry(booking["booking_id"]) == [booking["booking_id"]]
    assert status_of(client, token, booking["booking_id"]) == ("Cancelled", "Expired")

    free = client.get("/availability", params={"room_type": STAY["room_type"], "check_in": STAY["check_in"],
                                               "check_out": STAY["check_out"], "guests": STAY["adults"]})
    assert free.status_code == 200, free.text
    assert booking["room_number"] in free.json()["free_room_numbers"]

    assert run_expiry(booking["booking_id"]) == []        # running again changes nothing


def test_expired_booking_gives_its_discount_code_back(client, token, made):
    before = code_uses("PEARL500")
    response = book(client, token, made, code="PEARL500")
    assert response.status_code == 201, response.text
    booking_id = response.json()["booking_id"]
    assert code_uses("PEARL500") == before + 1

    made[-1] = (booking_id, None)                          # the job un-counts it, the cleanup must not do it again
    hold_is_over(booking_id)
    run_expiry(booking_id)
    assert code_uses("PEARL500") == before
