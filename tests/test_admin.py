import uuid

import pytest
from sqlalchemy import text

from tests.test_auth import STAFF, bearer, login
from tests.test_bookings import database
from tests.test_staff import admin_token, staff_token  # noqa: F401  (pytest fixtures)


@pytest.fixture
def new_staff():
    emails = []
    yield emails
    engine = database()
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM user_accounts WHERE email = ANY(:e)"), {"e": emails})
    engine.dispose()


def test_stats_for_the_last_30_days(client, admin_token):
    response = client.get("/admin/stats", headers=bearer(admin_token))
    assert response.status_code == 200, response.text
    stats = response.json()
    assert (stats["date_from"], stats["date_to"]) == ("2026-08-21", "2026-09-19")      # up to the hotel's today
    assert len(stats["daily"]) == 30 and 0 <= stats["occupancy"] <= 1
    assert stats["room_nights_sold"] == sum(day["rooms_sold"] for day in stats["daily"])
    assert abs(stats["revenue"] - sum(day["revenue"] for day in stats["daily"])) < 1
    assert abs(sum(c["revenue"] for c in stats["by_channel"]) - stats["revenue"]) < 1   # every night counted once
    if stats["room_nights_sold"]:
        assert abs(stats["adr"] - stats["revenue"] / stats["room_nights_sold"]) < 0.01


def test_stats_period_rules(client, admin_token, staff_token):
    one_day = client.get("/admin/stats", headers=bearer(admin_token),
                         params={"date_from": "2026-09-19", "date_to": "2026-09-19"}).json()
    assert len(one_day["daily"]) == 1
    backwards = client.get("/admin/stats", headers=bearer(admin_token),
                           params={"date_from": "2026-09-19", "date_to": "2026-09-01"})
    assert backwards.status_code == 400 and backwards.json()["detail"]["reason"] == "DATE_TO_BEFORE_DATE_FROM"
    too_long = client.get("/admin/stats", headers=bearer(admin_token),
                          params={"date_from": "2024-01-01", "date_to": "2026-09-19"})
    assert too_long.json()["detail"]["reason"] == "PERIOD_TOO_LONG"
    assert client.get("/admin/stats", headers=bearer(staff_token)).status_code == 403


def test_admin_manages_staff_accounts(client, admin_token, new_staff):
    email = f"salma.{uuid.uuid4().hex[:6]}@nilepearlhotel.example"
    added = client.post("/admin/staff", headers=bearer(admin_token),
                        json={"full_name": "Salma Adel", "email": email, "password": "Desk2026ok"})
    assert added.status_code == 201, added.text
    new_staff.append(email)
    account_id = added.json()["account_id"]
    assert added.json()["role"] == "Staff"
    assert login(client, email, "Desk2026ok").status_code == 200
    assert email in [s["email"] for s in client.get("/admin/staff", headers=bearer(admin_token)).json()]
    again = client.post("/admin/staff", headers=bearer(admin_token),
                        json={"full_name": "Salma Adel", "email": email, "password": "Desk2026ok"})
    assert again.status_code == 409

    client.post(f"/admin/staff/{account_id}/disable", headers=bearer(admin_token))
    disabled = login(client, email, "Desk2026ok")
    assert disabled.status_code == 403 and disabled.json()["detail"]["reason"] == "ACCOUNT_DISABLED"
    client.post(f"/admin/staff/{account_id}/enable", headers=bearer(admin_token))
    client.post(f"/admin/staff/{account_id}/password", headers=bearer(admin_token), json={"new_password": "Fresh2026ok"})
    assert login(client, email, "Fresh2026ok").status_code == 200


def test_admin_cannot_lock_themself_out(client, admin_token):
    me = client.get("/auth/me", headers=bearer(admin_token)).json()
    response = client.post(f"/admin/staff/{me['account_id']}/disable", headers=bearer(admin_token))
    assert response.status_code == 409 and response.json()["detail"]["reason"] == "CANNOT_DISABLE_YOURSELF"
    guest_account = client.post("/admin/staff/299/disable", headers=bearer(admin_token))     # Paul is a guest
    assert guest_account.status_code == 404
    assert login(client, STAFF).status_code == 200
