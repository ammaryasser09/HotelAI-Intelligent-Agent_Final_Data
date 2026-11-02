import re
import uuid

import pytest
from sqlalchemy import text

from tests.test_auth import GUEST, PASSWORD, bearer, login
from tests.test_bookings import database

STAY = {"room_type": "Single", "check_in": "2027-11-20", "check_out": "2027-11-21", "adults": 1}


@pytest.fixture
def accounts():
    """Accounts the test signs up are deleted afterwards (with their bookings and, if new, their guest record)."""
    made = []          # (email, delete the customer too?)
    yield made
    engine = database()
    with engine.begin() as connection:
        for email, new_customer in made:
            customer_id = connection.execute(text("SELECT customer_id FROM user_accounts WHERE email = :e"),
                                             {"e": email}).scalar()
            connection.execute(text("DELETE FROM user_accounts WHERE email = :e"), {"e": email})
            if customer_id and new_customer:
                connection.execute(text("DELETE FROM bookings WHERE customer_id = :c"), {"c": customer_id})
                connection.execute(text("DELETE FROM customers WHERE customer_id = :c"), {"c": customer_id})
    engine.dispose()


def new_guest(**changes):
    tag = uuid.uuid4().hex[:8]
    return {"first_name": "Mona", "last_name": "Hassan", "email": f"mona.{tag}@example.com",
            "phone": f"+2010{int(tag, 16) % 10**8:08d}", "password": "Pearl2026x", **changes}


def signup(client, accounts, new_customer=True, **changes):
    body = new_guest(**changes)
    response = client.post("/auth/signup", json=body)
    if response.status_code == 201:
        accounts.append((body["email"], new_customer))
    return body, response


def code_in(mail) -> str:
    return re.search(r"\b(\d{6})\b", mail["body"]).group(1)


def test_signup_then_confirm_the_email_with_the_code(client, accounts, outbox):
    body, response = signup(client, accounts)
    assert response.status_code == 201, response.text
    signed_up = response.json()
    assert signed_up["account"]["role"] == "Guest" and signed_up["account"]["email_verified"] is False
    token = signed_up["access_token"]

    [mail] = outbox
    assert mail["to"] == body["email"] and "verification code" in mail["subject"]
    code = code_in(mail)

    blocked = client.get("/me/bookings", headers=bearer(token))
    assert blocked.status_code == 403 and blocked.json()["detail"]["reason"] == "EMAIL_NOT_VERIFIED"

    wrong = client.post("/auth/verify-email", headers=bearer(token), json={"code": "000000" if code != "000000" else "111111"})
    assert wrong.status_code == 400 and wrong.json()["detail"] == {"reason": "WRONG_CODE", "attempts_left": 4}

    verified = client.post("/auth/verify-email", headers=bearer(token), json={"code": code})
    assert verified.status_code == 200, verified.text
    new_token = verified.json()["access_token"]
    assert verified.json()["account"]["email_verified"] is True
    assert client.get("/me/bookings", headers=bearer(new_token)).json() == []

    again = client.post("/auth/verify-email", headers=bearer(new_token), json={"code": code})
    assert again.status_code == 409 and again.json()["detail"]["reason"] == "ALREADY_VERIFIED"
    assert login(client, body["email"], "Pearl2026x").status_code == 200


def test_five_wrong_tries_end_the_code_and_a_new_one_works(client, accounts, outbox):
    _, response = signup(client, accounts)
    token = response.json()["access_token"]
    code = code_in(outbox[0])
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        client.post("/auth/verify-email", headers=bearer(token), json={"code": wrong})
    late = client.post("/auth/verify-email", headers=bearer(token), json={"code": code})
    assert late.status_code == 400 and late.json()["detail"]["reason"] == "CODE_EXPIRED"

    resent = client.post("/auth/verify-email/resend", headers=bearer(token))
    assert resent.status_code == 200 and resent.json()["expires_in_minutes"] == 10
    assert client.post("/auth/verify-email", headers=bearer(token), json={"code": code_in(outbox[-1])}).status_code == 200


def test_signups_that_are_refused(client, accounts):
    body, first = signup(client, accounts)
    assert first.status_code == 201
    same_email = client.post("/auth/signup", json=new_guest(email=body["email"].upper()))
    assert same_email.status_code == 409 and same_email.json()["detail"]["reason"] == "EMAIL_ALREADY_REGISTERED"
    pauls_email = client.post("/auth/signup", json=new_guest(email=GUEST))
    assert pauls_email.json()["detail"]["reason"] == "EMAIL_ALREADY_REGISTERED"
    pauls_phone = client.post("/auth/signup", json=new_guest(phone="+495012527971"))
    assert pauls_phone.status_code == 409 and pauls_phone.json()["detail"]["reason"] == "PHONE_ALREADY_REGISTERED"

    assert client.post("/auth/signup", json=new_guest(password="onlyletters")).status_code == 422
    assert client.post("/auth/signup", json=new_guest(email="not-an-email")).status_code == 422
    too_young = client.post("/auth/signup", json=new_guest(date_of_birth="2010-01-01"))
    assert too_young.status_code == 400 and too_young.json()["detail"] == {"reason": "TOO_YOUNG", "min_age": 18}


def test_date_of_birth_is_asked_before_the_first_booking(client, accounts, outbox):
    _, response = signup(client, accounts)
    token = response.json()["access_token"]
    token = client.post("/auth/verify-email", headers=bearer(token), json={"code": code_in(outbox[0])}).json()["access_token"]

    missing = client.post("/bookings", headers=bearer(token), json=STAY)
    assert missing.status_code == 400 and missing.json()["detail"]["reason"] == "DATE_OF_BIRTH_REQUIRED"
    young = client.post("/bookings", headers=bearer(token), json={**STAY, "date_of_birth": "2009-01-01"})
    assert young.status_code == 400 and young.json()["detail"]["reason"] == "TOO_YOUNG"

    first = client.post("/bookings", headers=bearer(token), json={**STAY, "date_of_birth": "1990-05-05"})
    assert first.status_code == 201, first.text
    later = client.post("/bookings", headers=bearer(token), json={**STAY, "check_in": "2027-11-22", "check_out": "2027-11-23"})
    assert later.status_code == 201, later.text                      # kept from the first booking


def test_a_guest_who_booked_by_phone_signs_up_and_sees_their_bookings(client, accounts, outbox):
    engine = database()
    with engine.connect() as connection:
        guest = connection.execute(text("""
            SELECT c.email, count(b.booking_id) AS bookings FROM customers c JOIN bookings b USING (customer_id)
            WHERE NOT EXISTS (SELECT 1 FROM user_accounts a WHERE a.customer_id = c.customer_id)
            GROUP BY c.email ORDER BY c.email LIMIT 1""")).mappings().one()
    engine.dispose()

    _, response = signup(client, accounts, new_customer=False, email=guest["email"])
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    token = client.post("/auth/verify-email", headers=bearer(token), json={"code": code_in(outbox[0])}).json()["access_token"]
    assert len(client.get("/me/bookings", headers=bearer(token)).json()) == guest["bookings"]


def test_forgot_password(client, accounts, outbox):
    body, _ = signup(client, accounts)
    outbox.clear()

    unknown = client.post("/auth/forgot-password", json={"email": "nobody.at.all@example.com"})
    known = client.post("/auth/forgot-password", json={"email": body["email"]})
    assert unknown.status_code == known.status_code == 200 and unknown.json() == known.json()   # nothing leaks
    [mail] = outbox
    assert "Reset your" in mail["subject"]

    reset = {"email": body["email"], "code": code_in(mail), "new_password": "NewPearl2026"}
    wrong = client.post("/auth/reset-password", json={**reset, "code": "000000" if reset["code"] != "000000" else "111111"})
    assert wrong.status_code == 400
    done = client.post("/auth/reset-password", json=reset)
    assert done.status_code == 200, done.text
    assert login(client, body["email"], "NewPearl2026").status_code == 200
    assert login(client, body["email"], "Pearl2026x").status_code == 401

    staff = client.post("/auth/forgot-password", json={"email": "karim.fathy@nilepearlhotel.example"})
    assert staff.status_code == 200 and len(outbox) == 1               # staff get no code: they ask the admin
    assert PASSWORD                                                    # the demo password is never changed here
