import os

import pytest
from fastapi.testclient import TestClient

# The tests send many requests from one address: raise the limit before the app reads its settings
os.environ["RATE_LIMIT"] = "10000/minute"
os.environ["LOGIN_RATE_LIMIT"] = "10000/minute"
os.environ["LINK_RATE_LIMIT"] = "10000/minute"
# The tests pay through the fake Paymob, whatever .env says (they turn the real one on only where needed)
os.environ["PAYMENT_PROVIDER"] = "mock"
# No background expiry while testing: the tests run it themselves, on their own bookings only
os.environ["EXPIRY_CHECK_SECONDS"] = "0"
# Emails are never really sent by the tests (see the outbox fixture below)
os.environ["EMAIL_PROVIDER"] = "log"
os.environ.setdefault("JWT_SECRET", "test-only-secret-not-used-anywhere-else")

from app.api.main import app  # noqa: E402


# One client (and one event loop) for the whole test run, so the database pool is reused safely.
@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    """Every test: emails to guests are collected in this list instead of being sent or written to logs/."""
    from app.api.services import email

    sent = []

    async def keep(to, subject, body):
        sent.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr(email, "deliver", keep)
    return sent
