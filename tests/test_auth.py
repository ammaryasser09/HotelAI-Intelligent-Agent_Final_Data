import pytest
from sqlalchemy import create_engine, text

from app.api.config import settings

PASSWORD = "NilePearl@2026"          # demo password of every account (database/README.md)
GUEST = "paul.fischer500@example.com"  # account 299, customer C000500: 2 own bookings + B005623 linked
STAFF = "karim.fathy@nilepearlhotel.example"


def login(client, email, password=PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def guest_token(client):
    response = login(client, GUEST)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_login(client):
    body = login(client, GUEST.upper()).json()          # email is not case sensitive
    assert body["token_type"] == "bearer"
    assert body["account"]["role"] == "Guest"
    assert body["account"]["customer_id"] == "C000500"
    assert "password_hash" not in body["account"]


def test_wrong_password_and_unknown_email_get_the_same_answer(client):
    wrong_password = login(client, GUEST, "wrong-password")
    unknown_email = login(client, "nobody@example.com")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json() == {"detail": {"reason": "INVALID_CREDENTIALS"}}


def test_me_needs_a_valid_token(client, guest_token):
    assert client.get("/auth/me", headers=bearer(guest_token)).json()["email"] == GUEST
    assert client.get("/auth/me").json()["detail"]["reason"] == "NOT_LOGGED_IN"
    assert client.get("/auth/me", headers=bearer("not.a.token")).json()["detail"]["reason"] == "INVALID_TOKEN"


def test_my_bookings(client, guest_token):
    bookings = client.get("/me/bookings", headers=bearer(guest_token)).json()
    access = {b["booking_id"]: b["access"] for b in bookings}
    assert access["B005623"] == "linked"
    assert list(access.values()).count("own") == 2
    check_ins = [b["check_in"] for b in bookings]
    assert check_ins == sorted(check_ins, reverse=True)      # newest first


def test_only_guests_have_bookings(client):
    staff_token = login(client, STAFF).json()["access_token"]
    response = client.get("/me/bookings", headers=bearer(staff_token))
    assert response.status_code == 403
    assert client.get("/me/bookings").status_code == 401


def test_link_booking_needs_proof(client, guest_token):
    url, headers = "/me/bookings/link", bearer(guest_token)
    assert client.post(url, headers=headers, json={"booking_ref": "B000004"}).status_code == 422
    wrong = client.post(url, headers=headers, json={"booking_ref": "B000004", "last_name": "Smith"})
    missing = client.post(url, headers=headers, json={"booking_ref": "B999999", "last_name": "Smith"})
    assert wrong.status_code == missing.status_code == 404
    assert wrong.json() == missing.json()


def test_link_booking_already_in_account(client, guest_token):
    body = client.post("/me/bookings/link", headers=bearer(guest_token),
                       json={"booking_ref": "B005623", "phone_last4": "0000"}).json()
    assert body["booking_id"] == "B005623" and body["access"] == "linked"


def test_link_booking_with_arabic_last_name(client, guest_token):
    # B000004 belongs to another guest (Almansoori / المنصوري); the test removes the link afterwards
    try:
        body = client.post("/me/bookings/link", headers=bearer(guest_token),
                           json={"booking_ref": "b000004", "last_name": "المنصوري"}).json()
        assert body["booking_id"] == "B000004" and body["access"] == "linked"
        ids = [b["booking_id"] for b in client.get("/me/bookings", headers=bearer(guest_token)).json()]
        assert "B000004" in ids
    finally:
        engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg"))
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM booking_links WHERE account_id = 299 AND booking_id = 'B000004'"))
        engine.dispose()


def test_personal_code_works_only_for_its_guest(client, guest_token):
    owner = login(client, "manon.robert571@example.com").json()["access_token"]   # PEARL6290 is hers
    assert client.get("/discount-codes/PEARL6290", headers=bearer(owner)).json()["usable"] is True
    other = client.get("/discount-codes/PEARL6290", headers=bearer(guest_token)).json()
    assert other["reason"] == "PERSONAL_CODE_OF_ANOTHER_GUEST"
