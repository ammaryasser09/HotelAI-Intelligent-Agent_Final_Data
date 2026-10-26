import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.api.config import settings
from tests.test_auth import GUEST, bearer, login

# Far-future dates, so the demo data leaves Double rooms free
STAY = {"room_type": "Double", "check_in": "2027-11-10", "check_out": "2027-11-13", "adults": 2}


def database():
    return create_engine(make_url(settings.database_url).set(drivername="postgresql+psycopg"))


@pytest.fixture(scope="module")
def token(client):
    return login(client, GUEST).json()["access_token"]


@pytest.fixture
def made():
    """Bookings a test creates are deleted afterwards (payments go with them), and codes uncounted."""
    created = []
    yield created
    engine = database()
    with engine.begin() as connection:
        for booking_id, code in created:
            connection.execute(text("DELETE FROM bookings WHERE booking_id = :b"), {"b": booking_id})
            if code:
                connection.execute(text("""
                    UPDATE discount_codes SET usage_count = usage_count - 1,
                           status = CASE WHEN status = 'Exhausted' THEN 'Active' ELSE status END
                    WHERE discount_code = :c"""), {"c": code})
    engine.dispose()


def book(client, token, made, code=None, **changes):
    body = {**STAY, **changes}
    if code:
        body["discount_code"] = code
    response = client.post("/bookings", headers=bearer(token), json=body)
    if response.status_code == 201:
        used = response.json()["discount"] or {}
        made.append((response.json()["booking_id"], used.get("code")))
    return response


def test_flexible_booking_waits_for_the_deposit_then_mock_payment_confirms_it(client, token, made):
    response = book(client, token, made)
    assert response.status_code == 201, response.text
    booking = response.json()
    assert booking["booking_status"] == "Pending"
    assert booking["amount_due"] == 24000                  # 3 nights x 8,000
    assert booking["pay_now"] == 8000                      # deposit = one night
    assert booking["pay_at_hotel"] == 16000
    assert "/payments/mock/" in booking["payment_url"]

    mine = {b["booking_id"]: b for b in client.get("/me/bookings", headers=bearer(token)).json()}
    assert mine[booking["booking_id"]]["booking_status"] == "Pending"

    paid = client.post(f"/payments/mock/{booking['booking_id']}/pay")
    assert paid.status_code == 200, paid.text
    assert paid.json()["booking_status"] == "Confirmed" and paid.json()["amount_paid"] == 8000

    mine = {b["booking_id"]: b for b in client.get("/me/bookings", headers=bearer(token)).json()}
    assert mine[booking["booking_id"]]["booking_status"] == "Confirmed"
    assert mine[booking["booking_id"]]["amount_paid"] == 8000

    again = client.post(f"/payments/mock/{booking['booking_id']}/pay")
    assert again.status_code == 409


def test_mock_payment_page_opens(client, token, made):
    booking = book(client, token, made).json()
    page = client.get(f"/payments/mock/{booking['booking_id']}")
    assert page.status_code == 200
    assert booking["booking_id"] in page.text and "8,000.00" in page.text


def test_non_refundable_is_paid_in_full_and_takes_no_code(client, token, made):
    booking = book(client, token, made, code="PEARL100", rate_plan="Non-refundable").json()
    assert booking["price_per_night"] == 6800              # 8,000 x 0.85
    assert booking["discount"] is None
    assert booking["discount_code_not_used"] == "NOT_ON_NON_REFUNDABLE"
    assert booking["pay_now"] == booking["amount_due"] == 20400
    assert booking["pay_at_hotel"] == 0


def test_a_used_code_is_counted(client, token, made):
    engine = database()
    count = "SELECT usage_count FROM discount_codes WHERE discount_code = 'PEARL500'"
    with engine.connect() as connection:
        before = connection.execute(text(count)).scalar_one()
    booking = book(client, token, made, code="PEARL500").json()
    with engine.connect() as connection:
        after = connection.execute(text(count)).scalar_one()
    engine.dispose()
    assert booking["discount"] == {"source": "Code", "code": "PEARL500", "amount": 1500}
    assert booking["amount_due"] == 22500
    assert after == before + 1


def test_long_stay_discount_is_stored(client, token, made):
    booking = book(client, token, made, check_out="2027-11-18").json()   # 8 nights
    assert booking["discount"]["source"] == "Long Stay"
    assert booking["amount_due"] == 64000 - 7680


def test_booking_is_refused_when_it_cannot_be_made(client, token):
    assert client.post("/bookings", json=STAY).status_code == 401
    full = client.post("/bookings", headers=bearer(token),
                       json={**STAY, "check_in": "2026-12-24", "check_out": "2026-12-27"})
    assert full.status_code == 409 and full.json()["detail"]["reason"] == "NO_ROOM_AVAILABLE"
    crowded = client.post("/bookings", headers=bearer(token), json={**STAY, "children": 1})
    assert crowded.status_code == 400 and crowded.json()["detail"]["reason"] == "CAPACITY_EXCEEDED"
    past = client.post("/bookings", headers=bearer(token),
                       json={**STAY, "check_in": "2026-09-01", "check_out": "2026-09-03"})
    assert past.json()["detail"]["reason"] == "CHECK_IN_IN_THE_PAST"
