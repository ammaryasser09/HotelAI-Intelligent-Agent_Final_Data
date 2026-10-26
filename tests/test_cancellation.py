import pytest
from sqlalchemy import text

from tests.test_auth import bearer
from tests.test_bookings import book, database, made, token  # noqa: F401  (pytest fixtures)
from tests.test_expiry import code_uses


def quote(client, token, booking_id):
    return client.get(f"/me/bookings/{booking_id}/cancellation", headers=bearer(token))


def cancel(client, token, booking_id):
    return client.post(f"/me/bookings/{booking_id}/cancel", headers=bearer(token))


def mine(client, token, booking_id):
    return {b["booking_id"]: b for b in client.get("/me/bookings", headers=bearer(token)).json()}[booking_id]


@pytest.fixture
def free_window_already_over():
    """Makes the free-cancellation window so long that every booking is already past it, then puts it back."""
    engine = database()
    with engine.begin() as connection:
        before = connection.execute(text("SELECT value FROM app_settings WHERE key = 'free_cancellation_hours'")).scalar_one()
        connection.execute(text("UPDATE app_settings SET value = '100000' WHERE key = 'free_cancellation_hours'"))
    yield
    with engine.begin() as connection:
        connection.execute(text("UPDATE app_settings SET value = :v WHERE key = 'free_cancellation_hours'"), {"v": before})
    engine.dispose()


def test_free_cancellation_gives_the_whole_deposit_back(client, token, made):
    booking_id = book(client, token, made).json()["booking_id"]       # arrives 2027-11-10

    terms = quote(client, token, booking_id).json()
    assert terms["is_free"] and terms["free_cancellation_until"] == "2027-11-08T15:00:00"   # 48 h before 3 PM
    assert terms["amount_paid"] == 0 and terms["refund"] == 0

    client.post(f"/payments/mock/{booking_id}/pay")
    terms = quote(client, token, booking_id).json()
    assert (terms["amount_paid"], terms["charge"], terms["refund"]) == (8000, 0, 8000)

    done = cancel(client, token, booking_id)
    assert done.status_code == 200, done.text
    assert done.json() == {"booking_id": booking_id, "booking_status": "Cancelled",
                           "payment_status": "Refunded", "charge": 0, "refund": 8000}
    assert mine(client, token, booking_id)["refund_amount"] == 8000

    again = cancel(client, token, booking_id)
    assert again.status_code == 409 and again.json()["detail"]["reason"] == "NOT_CANCELLABLE"


def test_late_cancellation_keeps_the_first_night(client, token, made, free_window_already_over):
    booking_id = book(client, token, made).json()["booking_id"]
    client.post(f"/payments/mock/{booking_id}/pay")

    terms = quote(client, token, booking_id).json()
    assert not terms["is_free"] and (terms["charge"], terms["refund"]) == (8000, 0)

    done = cancel(client, token, booking_id).json()
    assert (done["payment_status"], done["charge"], done["refund"]) == ("Paid", 8000, 0)


def test_non_refundable_gives_nothing_back(client, token, made):
    booking_id = book(client, token, made, rate_plan="Non-refundable").json()["booking_id"]
    client.post(f"/payments/mock/{booking_id}/pay")

    terms = quote(client, token, booking_id).json()
    assert terms["free_cancellation_until"] is None and not terms["is_free"]
    assert (terms["amount_paid"], terms["charge"], terms["refund"]) == (20400, 20400, 0)
    assert cancel(client, token, booking_id).json()["refund"] == 0


def test_unpaid_booking_cancels_for_free_and_gives_its_code_back(client, token, made):
    before = code_uses("PEARL500")
    booking_id = book(client, token, made, code="PEARL500").json()["booking_id"]
    made[-1] = (booking_id, None)                     # the cancellation un-counts the code, the cleanup must not

    done = cancel(client, token, booking_id).json()
    assert (done["payment_status"], done["charge"], done["refund"]) == ("Expired", 0, 0)
    assert code_uses("PEARL500") == before
    assert client.post(f"/payments/mock/{booking_id}/pay").status_code == 409     # the link is closed


def test_only_your_own_bookings_can_be_cancelled(client, token):
    assert quote(client, token, "B000001").status_code == 404        # another guest's booking
    assert cancel(client, token, "B000001").status_code == 404
    assert client.post("/me/bookings/B000001/cancel").status_code == 401
