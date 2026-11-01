import pytest
from sqlalchemy import text

from tests.test_auth import GUEST, PASSWORD, STAFF, bearer, login
from tests.test_bookings import book, database, made, token  # noqa: F401  (pytest fixtures)

ADMIN = "admin@nilepearlhotel.example"


@pytest.fixture(scope="module")
def staff_token(client):
    return login(client, STAFF).json()["access_token"]


@pytest.fixture(scope="module")
def admin_token(client):
    return login(client, ADMIN, PASSWORD).json()["access_token"]


@pytest.fixture
def opened():
    """Tickets the test opens are deleted afterwards, with any discount code they issued."""
    ids = []
    yield ids
    engine = database()
    with engine.begin() as connection:
        codes = connection.execute(text("""DELETE FROM customer_requests WHERE request_id = ANY(:ids)
                                           RETURNING issued_code_id"""), {"ids": ids}).scalars().all()
        connection.execute(text("DELETE FROM discount_codes WHERE code_id = ANY(:codes)"), {"codes": [c for c in codes if c]})
    engine.dispose()


@pytest.fixture
def stay_put_back():
    """A demo stay the test checks in and out is put back exactly as it was."""
    saved = []

    def remember(booking_id):
        engine = database()
        with engine.connect() as connection:
            saved.append(connection.execute(text("""
                SELECT b.booking_id, b.booking_status, b.checked_in_at, b.checked_out_at, b.room_number,
                       p.amount_paid, p.payment_status, p.payment_method, r.status AS room_status
                FROM bookings b JOIN payments p USING (booking_id) JOIN rooms r USING (room_number)
                WHERE b.booking_id = :b"""), {"b": booking_id}).mappings().one())
        engine.dispose()

    yield remember
    engine = database()
    with engine.begin() as connection:
        for s in saved:
            connection.execute(text("""UPDATE bookings SET booking_status = :booking_status, checked_out_at = :checked_out_at,
                                       checked_in_at = :checked_in_at WHERE booking_id = :booking_id"""), dict(s))
            connection.execute(text("""UPDATE payments SET amount_paid = :amount_paid, payment_status = :payment_status,
                                       payment_method = :payment_method WHERE booking_id = :booking_id"""), dict(s))
            connection.execute(text("UPDATE rooms SET status = :room_status WHERE room_number = :room_number"), dict(s))
    engine.dispose()


def ask(client, token, opened, **body):
    response = client.post("/requests", headers=bearer(token), json=body)
    assert response.status_code == 201, response.text
    opened.append(response.json()["request_id"])
    return response.json()["request_id"]


def test_each_role_sees_only_its_part(client, token, staff_token, admin_token):
    guest = client.get("/staff/arrivals", headers=bearer(token))
    assert guest.status_code == 403 and guest.json()["detail"]["reason"] == "STAFF_ONLY"
    assert client.get("/staff/arrivals").status_code == 401
    staff = client.get("/admin/discount-requests", headers=bearer(staff_token))
    assert staff.status_code == 403 and staff.json()["detail"]["reason"] == "ADMIN_ONLY"
    assert client.get("/staff/arrivals", headers=bearer(admin_token)).status_code == 200    # the admin is staff too


def test_check_in_then_check_out_with_the_balance(client, staff_token, stay_put_back):
    arrivals = client.get("/staff/arrivals", headers=bearer(staff_token)).json()
    assert arrivals, "the demo data has guests arriving today"
    guest = arrivals[0]
    stay_put_back(guest["booking_id"])

    checked_in = client.post(f"/staff/bookings/{guest['booking_id']}/check-in", headers=bearer(staff_token))
    assert checked_in.status_code == 200, checked_in.text
    assert guest["booking_id"] not in [a["booking_id"] for a in client.get("/staff/arrivals", headers=bearer(staff_token)).json()]
    in_house = {s["booking_id"]: s for s in client.get("/staff/in-house", headers=bearer(staff_token)).json()}
    assert in_house[guest["booking_id"]]["balance_due"] == guest["balance_due"]
    again = client.post(f"/staff/bookings/{guest['booking_id']}/check-in", headers=bearer(staff_token))
    assert again.status_code == 409 and again.json()["detail"]["reason"] == "ALREADY_CHECKED_IN"

    out = client.post(f"/staff/bookings/{guest['booking_id']}/check-out", headers=bearer(staff_token),
                      json={"payment_method": "Cash"})
    assert out.status_code == 200, out.text
    assert out.json()["booking_status"] == "Completed" and out.json()["balance_paid"] == guest["balance_due"]
    gone = client.post(f"/staff/bookings/{guest['booking_id']}/check-out", headers=bearer(staff_token), json={})
    assert gone.status_code == 409 and gone.json()["detail"]["reason"] == "NOT_CONFIRMED"


def test_no_check_in_before_the_arrival_day(client, token, made, staff_token):
    booking_id = book(client, token, made).json()["booking_id"]        # arrives in 2027
    client.post(f"/payments/mock/{booking_id}/pay")
    early = client.post(f"/staff/bookings/{booking_id}/check-in", headers=bearer(staff_token))
    assert early.status_code == 409 and early.json()["detail"]["reason"] == "NOT_ARRIVAL_DAY_YET"
    out = client.post(f"/staff/bookings/{booking_id}/check-out", headers=bearer(staff_token), json={})
    assert out.json()["detail"]["reason"] == "NOT_CHECKED_IN"


def test_ticket_queue_take_and_close(client, token, staff_token, opened):
    towels = ask(client, token, opened, request_type="Housekeeping", request_text="Two extra towels", booking_id="B011936")
    emergency = client.post("/requests/emergency", json={"request_text": "Smoke on floor 3"}).json()["request"]
    opened.append(emergency["request_id"])

    queue = client.get("/staff/requests", headers=bearer(staff_token)).json()
    assert queue[0]["priority"] == "Critical"                       # emergencies first
    mine = {t["request_id"]: t for t in queue}[towels]
    assert mine["guest_name"] == "Paul Fischer" and mine["request_status"] == "Open"

    taken = client.post(f"/staff/requests/{towels}/take", headers=bearer(staff_token)).json()
    assert (taken["request_status"], taken["handled_by"]) == ("In Progress", "Karim Fathy")
    again = client.post(f"/staff/requests/{towels}/take", headers=bearer(staff_token))
    assert again.status_code == 409 and again.json()["detail"]["reason"] == "ALREADY_TAKEN"

    done = client.post(f"/staff/requests/{towels}/close", headers=bearer(staff_token), json={"outcome": "Resolved"})
    assert done.json()["request_status"] == "Resolved"
    status = {r["request_id"]: r for r in client.get("/me/requests", headers=bearer(token)).json()}[towels]
    assert status["request_status"] == "Resolved"                  # the guest sees it too
    assert client.post(f"/staff/requests/{towels}/close", headers=bearer(staff_token), json={}).json()["detail"]["reason"] == "ALREADY_CLOSED"


def test_special_request_decision(client, token, staff_token, opened):
    special = ask(client, token, opened, request_type="Special Request", category="Celebration Arrangement",
                  booking_id="B011936", request_text="A birthday cake on arrival")
    approved = client.post(f"/staff/requests/{special}/decision", headers=bearer(staff_token), json={"decision": "Approved"})
    assert approved.json()["request_status"] == "In Progress" and approved.json()["decision"] == "Approved"
    twice = client.post(f"/staff/requests/{special}/decision", headers=bearer(staff_token), json={"decision": "Rejected"})
    assert twice.json()["detail"]["reason"] == "ALREADY_DECIDED"

    towels = ask(client, token, opened, request_type="Housekeeping", request_text="Towels")
    wrong = client.post(f"/staff/requests/{towels}/decision", headers=bearer(staff_token), json={"decision": "Approved"})
    assert wrong.json()["detail"]["reason"] == "NOT_A_SPECIAL_REQUEST"


def test_the_admin_answers_discount_requests(client, token, staff_token, admin_token, opened, outbox):
    asked = ask(client, token, opened, request_type="Discount Request", request_text="I stay with you every year")
    staff_close = client.post(f"/staff/requests/{asked}/close", headers=bearer(staff_token), json={})
    assert staff_close.status_code == 409 and staff_close.json()["detail"]["reason"] == "ADMIN_DECIDES"
    assert asked in [r["request_id"] for r in client.get("/admin/discount-requests", headers=bearer(admin_token)).json()]

    approved = client.post(f"/admin/discount-requests/{asked}/approve", headers=bearer(admin_token),
                           json={"discount_type": "PERCENTAGE", "discount_value": 10})
    assert approved.status_code == 200, approved.text
    code = approved.json()["discount_code"]
    assert code.startswith("NP") and approved.json()["valid_to"] == "2026-10-19"     # 30 days from the hotel's today
    assert outbox[-1]["to"] == GUEST and code in outbox[-1]["body"] and "10% off" in outbox[-1]["body"]

    mine = {r["request_id"]: r for r in client.get("/me/requests", headers=bearer(token)).json()}[asked]
    assert (mine["decision"], mine["discount_code"]) == ("Approved", code)
    assert client.get(f"/discount-codes/{code}", headers=bearer(token)).json()["usable"] is True     # his own code
    assert client.get(f"/discount-codes/{code}").json()["usable"] is False                          # nobody else's
    assert client.post(f"/admin/discount-requests/{asked}/approve", headers=bearer(admin_token),
                       json={"discount_value": 10}).status_code == 404                               # answered already

    second = ask(client, token, opened, request_type="Discount Request", request_text="Can I get 50% off?")
    rejected = client.post(f"/admin/discount-requests/{second}/reject", headers=bearer(admin_token))
    assert rejected.json()["decision"] == "Rejected" and outbox[-1]["subject"] == "About your discount request"
    assert client.post(f"/admin/discount-requests/{second}/approve", headers=bearer(admin_token),
                       json={"discount_type": "PERCENTAGE", "discount_value": 120}).status_code == 422
