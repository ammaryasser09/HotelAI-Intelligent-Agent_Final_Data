import asyncio

from app.api.services import email
from app.api.services.email import deliver as real_deliver
from tests.test_auth import GUEST, bearer
from tests.test_bookings import book, made, token  # noqa: F401  (pytest fixtures)
from tests.test_expiry import hold_is_over, run_expiry


def test_payment_sends_the_confirmation(client, token, made, outbox):
    booking_id = book(client, token, made).json()["booking_id"]
    assert outbox == []                                              # nothing yet: the booking waits for payment
    client.post(f"/payments/mock/{booking_id}/pay")

    [mail] = outbox
    assert mail["to"] == GUEST
    assert mail["subject"] == f"Your booking {booking_id} is confirmed"
    assert "Dear Paul Fischer" in mail["body"]
    assert "Stay total: 24,000.00 EGP" in mail["body"] and "To pay at the hotel: 16,000.00 EGP" in mail["body"]


def test_change_and_cancel_send_their_emails(client, token, made, outbox):
    booking_id = book(client, token, made).json()["booking_id"]
    client.post(f"/payments/mock/{booking_id}/pay")
    client.post(f"/me/bookings/{booking_id}/change", headers=bearer(token), json={"check_out": "2027-11-14"})
    client.post(f"/me/bookings/{booking_id}/cancel", headers=bearer(token))

    assert [m["subject"].split()[-1] for m in outbox] == ["confirmed", "changed", "cancelled"]
    assert "Sun 14 Nov 2027" in outbox[1]["body"]                    # the new check-out
    assert "Refunded to your card: 8,000.00 EGP" in outbox[2]["body"]


def test_expired_booking_gets_told(client, token, made, outbox):
    booking_id = book(client, token, made).json()["booking_id"]
    hold_is_over(booking_id)
    run_expiry(booking_id)
    assert outbox[-1]["subject"] == f"Your booking {booking_id} was cancelled: payment not received"


def test_a_failing_email_never_undoes_the_payment(client, token, made, monkeypatch):
    async def broken(to, subject, body):
        raise ConnectionError("mail server down")
    monkeypatch.setattr(email, "deliver", broken)

    booking_id = book(client, token, made).json()["booking_id"]
    paid = client.post(f"/payments/mock/{booking_id}/pay")
    assert paid.status_code == 200 and paid.json()["booking_status"] == "Confirmed"


def test_log_mode_writes_the_email_to_a_file(tmp_path, monkeypatch):
    monkeypatch.setattr(email, "EMAIL_DIR", tmp_path)
    asyncio.run(real_deliver("guest@example.com", "Your booking B000123 is confirmed", "Hello"))
    [written] = tmp_path.iterdir()
    assert written.name.endswith("-B000123.txt")
    assert written.read_text(encoding="utf-8").startswith("To: guest@example.com\nSubject: Your booking B000123")
