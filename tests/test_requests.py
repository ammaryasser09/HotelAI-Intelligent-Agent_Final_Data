import uuid

import pytest
from sqlalchemy import text

from tests.test_auth import PASSWORD, bearer, login
from tests.test_bookings import database, token  # noqa: F401  (pytest fixture: Paul's login)


@pytest.fixture
def opened():
    """Tickets the test opens are deleted afterwards."""
    ids = []
    yield ids
    engine = database()
    with engine.begin() as connection:
        calls = connection.execute(text("DELETE FROM customer_requests WHERE request_id = ANY(:ids) RETURNING call_id"),
                                   {"ids": ids}).scalars().all()
        connection.execute(text("DELETE FROM calls WHERE call_id = ANY(:calls)"), {"calls": [c for c in calls if c]})
    engine.dispose()


def ask(client, token, opened, **body):
    response = client.post("/requests", headers=bearer(token), json=body)
    if response.status_code == 201:
        opened.append(response.json()["request_id"])
    return response


def test_guest_requests_become_tickets(client, token, opened):
    towels = ask(client, token, opened, request_type="Housekeeping", request_text="Two extra towels please",
                 booking_id="B011936")
    assert towels.status_code == 201, towels.text
    assert (towels.json()["priority"], towels.json()["request_status"]) == ("Normal", "Open")

    callback = ask(client, token, opened, request_type="Staff Callback", request_text="Please call me back")
    assert callback.json()["priority"] == "Urgent"
    complaint = ask(client, token, opened, request_type="Complaint", category="Room Issue", request_text="The AC is noisy")
    assert complaint.status_code == 201

    mine = [r["request_id"] for r in client.get("/me/requests", headers=bearer(token)).json()]
    assert set(opened) <= set(mine)


def test_requests_that_are_refused(client, token, opened):
    reasons = {
        "BOOKING_REQUIRED": ask(client, token, opened, request_type="Special Request", category="Room Preference",
                                request_text="High floor please"),
        "WRONG_CATEGORY": ask(client, token, opened, request_type="Special Request", category="Spa",
                              booking_id="B011936", request_text="High floor please"),
        "NO_CATEGORY_FOR_THIS_TYPE": ask(client, token, opened, request_type="Housekeeping", category="Room Issue",
                                         request_text="Towels"),
        "BOOKING_NOT_FOUND": ask(client, token, opened, request_type="Housekeeping", booking_id="B000001",
                                 request_text="Towels"),          # another guest's booking
    }
    for reason, response in reasons.items():
        assert response.json()["detail"]["reason"] == reason, response.text
    assert ask(client, token, opened, request_type="Free Upgrade", request_text="please").status_code == 422
    assert client.post("/requests", json={"request_type": "Housekeeping", "request_text": "Towels"}).status_code == 401


def test_anyone_can_raise_an_emergency(client, token, opened):
    visitor = client.post("/requests/emergency", json={"request_text": "Someone fainted in the lobby"})
    assert visitor.status_code == 201, visitor.text
    opened.append(visitor.json()["request"]["request_id"])
    assert visitor.json()["request"]["priority"] == "Critical"
    assert (visitor.json()["ambulance"], visitor.json()["police"], visitor.json()["fire"]) == ("123", "122", "180")
    assert visitor.json()["request"]["call_id"]                    # the website emergency got its own call record
    unknown_call = client.post("/requests/emergency", json={"request_text": "Help", "call_id": str(uuid.uuid4())})
    assert unknown_call.status_code == 404 and unknown_call.json()["detail"]["reason"] == "CALL_NOT_FOUND"

    guest = client.post("/requests/emergency", headers=bearer(token), json={"request_text": "Smoke in the corridor"})
    opened.append(guest.json()["request"]["request_id"])
    assert guest.json()["request"]["request_id"] in [r["request_id"] for r in client.get("/me/requests", headers=bearer(token)).json()]


def test_loyalty(client, token):
    assert client.get("/me/loyalty", headers=bearer(token)).json() == {     # Paul is not a member
        "member": False, "tier": None, "points_balance": None, "points_worth_egp": None,
        "total_stays": None, "late_checkout_until": None, "benefits": None}

    engine = database()
    with engine.connect() as connection:
        gold = connection.execute(text("""
            SELECT a.email, m.points_balance FROM loyalty_members m JOIN user_accounts a USING (customer_id)
            WHERE m.tier = 'Gold' AND m.status = 'Active' AND a.is_active ORDER BY a.email LIMIT 1""")).mappings().one()
    engine.dispose()
    gold_token = login(client, gold["email"], PASSWORD).json()["access_token"]
    status = client.get("/me/loyalty", headers=bearer(gold_token)).json()
    assert status["member"] and status["tier"] == "Gold" and status["late_checkout_until"] == "14:00"
    assert status["points_worth_egp"] == (gold["points_balance"] // 1000) * 500     # 1,000 points = 500 EGP
