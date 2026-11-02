import hashlib
import hmac as hmac_lib
import json

import httpx
import pytest

from app.api.config import settings
from app.api.services import payments
from tests.test_bookings import book, made, token  # noqa: F401  (pytest fixtures)
from tests.test_auth import bearer

SECRET = "test-hmac-secret"


@pytest.fixture
def paymob(monkeypatch):
    """Turns the real-Paymob code on with made-up keys. Nothing reaches Paymob: a fake answers instead.
    The test can read what we sent in paymob["sent"] or make the fake fail with paymob["down"] = True."""
    monkeypatch.setattr(settings, "payment_provider", "paymob")
    monkeypatch.setattr(settings, "paymob_hmac_secret", SECRET)
    monkeypatch.setattr(settings, "paymob_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "paymob_api_key", "api_key_fake")
    monkeypatch.setattr(settings, "paymob_public_key", "pk_test_fake")
    monkeypatch.setattr(settings, "paymob_integration_id", 123456)
    monkeypatch.setattr(settings, "public_base_url", "https://example.ngrok-free.app")
    fake = {"down": False, "refunds": []}

    def fake_paymob(request: httpx.Request):
        if fake["down"]:
            raise httpx.ConnectError("no internet")
        if str(request.url) == settings.paymob_auth_url:
            return httpx.Response(201, json={"token": "auth_token_fake"})
        if str(request.url) == settings.paymob_refund_url:
            fake["refunds"].append(json.loads(request.read()))
            return httpx.Response(201, json={"type": "TRANSACTION", "obj": {"id": 1, "success": True}})
        fake["sent"] = {"auth": request.headers["Authorization"], "body": request.read()}
        return httpx.Response(201, json={"client_secret": "csk_test_123", "intention_order_id": 1})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(payments.httpx, "AsyncClient",
                        lambda **kw: real_client(transport=httpx.MockTransport(fake_paymob), **kw))
    return fake


def transaction(booking_id, amount_cents, success=True, pending=False):
    """A callback shaped like the one Paymob sends after a payment."""
    return {
        "amount_cents": amount_cents, "created_at": "2026-10-27T12:00:00.000000", "currency": "EGP",
        "error_occured": False, "has_parent_transaction": False, "id": 987654, "integration_id": 123456,
        "is_3d_secure": True, "is_auth": False, "is_capture": False, "is_refunded": False,
        "is_standalone_payment": True, "is_voided": False, "owner": 11111, "pending": pending,
        "success": success,
        "order": {"id": 555555, "merchant_order_id": f"{booking_id}-ab12cd34"},
        "source_data": {"pan": "2346", "sub_type": "MasterCard", "type": "card"},
    }


def sign(obj):
    fields = [obj["amount_cents"], obj["created_at"], obj["currency"], obj["error_occured"],
              obj["has_parent_transaction"], obj["id"], obj["integration_id"], obj["is_3d_secure"],
              obj["is_auth"], obj["is_capture"], obj["is_refunded"], obj["is_standalone_payment"],
              obj["is_voided"], obj["order"]["id"], obj["owner"], obj["pending"], obj["source_data"]["pan"],
              obj["source_data"]["sub_type"], obj["source_data"]["type"], obj["success"]]
    text = "".join(str(f).lower() if isinstance(f, bool) else str(f) for f in fields)
    return hmac_lib.new(SECRET.encode(), text.encode(), hashlib.sha512).hexdigest()


def status_of(client, token, booking_id):
    mine = {b["booking_id"]: b for b in client.get("/me/bookings", headers=bearer(token)).json()}
    return mine[booking_id]["booking_status"]


def test_signature_matches_paymob_rules_and_any_change_breaks_it(paymob):
    obj = transaction("B999999", 800000)
    assert payments.paymob_signature_is_valid(obj, sign(obj))
    obj["amount_cents"] = 100                     # someone changed the amount on the way
    assert not payments.paymob_signature_is_valid(obj, sign(transaction("B999999", 800000)))
    assert not payments.paymob_signature_is_valid(obj, "")


def test_booking_gets_a_paymob_checkout_link(client, token, made, paymob):
    response = book(client, token, made)
    assert response.status_code == 201, response.text
    url = response.json()["payment_url"]
    assert url.startswith(settings.paymob_checkout_url)
    assert "publicKey=pk_test_fake" in url and "clientSecret=csk_test_123" in url
    assert paymob["sent"]["auth"] == "Token sk_test_fake"
    sent = json.loads(paymob["sent"]["body"])
    assert sent["amount"] == 800000                                # 8,000 EGP deposit, in piasters
    assert sent["notification_url"] == "https://example.ngrok-free.app/payments/paymob/webhook"
    assert sent["special_reference"].startswith(response.json()["booking_id"] + "-")


def test_paymob_down_means_no_booking(client, token, made, paymob):
    paymob["down"] = True
    before = len(client.get("/me/bookings", headers=bearer(token)).json())
    response = book(client, token, made)
    assert response.status_code == 502
    assert response.json()["detail"]["reason"] == "PAYMENT_PROVIDER_ERROR"
    assert len(client.get("/me/bookings", headers=bearer(token)).json()) == before


def test_webhook_confirms_only_a_correctly_signed_successful_payment(client, token, made, paymob):
    booking_id = book(client, token, made).json()["booking_id"]
    hook = "/payments/paymob/webhook"

    forged = transaction(booking_id, 800000)
    assert client.post(hook, params={"hmac": "0" * 128},
                       json={"type": "TRANSACTION", "obj": forged}).status_code == 403
    assert status_of(client, token, booking_id) == "Pending"

    failed = transaction(booking_id, 800000, success=False)
    assert client.post(hook, params={"hmac": sign(failed)},
                       json={"type": "TRANSACTION", "obj": failed}).status_code == 200
    assert status_of(client, token, booking_id) == "Pending"

    too_little = transaction(booking_id, 100)
    client.post(hook, params={"hmac": sign(too_little)}, json={"type": "TRANSACTION", "obj": too_little})
    assert status_of(client, token, booking_id) == "Pending"

    paid = transaction(booking_id, 800000)
    assert client.post(hook, params={"hmac": sign(paid)},
                       json={"type": "TRANSACTION", "obj": paid}).status_code == 200
    assert status_of(client, token, booking_id) == "Confirmed"

    # Paymob may send the same callback twice: still 200, nothing changes
    assert client.post(hook, params={"hmac": sign(paid)},
                       json={"type": "TRANSACTION", "obj": paid}).status_code == 200

    page = client.get("/payments/paymob/return", params={"merchant_order_id": f"{booking_id}-ab12cd34",
                                                        "success": "true"})
    assert page.status_code == 200 and booking_id in page.text


def test_paymob_endpoints_are_hidden_in_mock_mode(client):
    assert client.post("/payments/paymob/webhook", json={}).status_code == 404


def test_cancelling_a_paymob_booking_sends_the_money_back_through_paymob(client, token, made, paymob):
    booking_id = book(client, token, made).json()["booking_id"]
    paid = transaction(booking_id, 800000)                       # Paymob's transaction id is 987654
    client.post("/payments/paymob/webhook", params={"hmac": sign(paid)}, json={"type": "TRANSACTION", "obj": paid})

    cancelled = client.post(f"/me/bookings/{booking_id}/cancel", headers=bearer(token))
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["refund"] == 8000                    # far from arrival: free, all of it back
    assert paymob["refunds"] == [{"auth_token": "auth_token_fake", "transaction_id": 987654, "amount_cents": 800000}]

    # Paymob then calls back about the refund itself: accepted, nothing changes
    refund = {**transaction(booking_id, 800000), "id": 987655, "has_parent_transaction": True}
    assert client.post("/payments/paymob/webhook", params={"hmac": sign(refund)},
                       json={"type": "TRANSACTION", "obj": refund}).status_code == 200
    assert status_of(client, token, booking_id) == "Cancelled"


def test_refund_refused_by_paymob_leaves_the_booking_as_it_was(client, token, made, paymob):
    booking_id = book(client, token, made).json()["booking_id"]
    paid = transaction(booking_id, 800000)
    client.post("/payments/paymob/webhook", params={"hmac": sign(paid)}, json={"type": "TRANSACTION", "obj": paid})

    paymob["down"] = True
    response = client.post(f"/me/bookings/{booking_id}/cancel", headers=bearer(token))
    assert response.status_code == 502 and response.json()["detail"]["reason"] == "REFUND_FAILED"
    assert status_of(client, token, booking_id) == "Confirmed"
