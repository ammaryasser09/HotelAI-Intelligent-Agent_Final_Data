import os

import pytest
from fastapi.testclient import TestClient

# The tests send many requests from one address: raise the limit before the app reads its settings
os.environ["RATE_LIMIT"] = "10000/minute"

from app.api.main import app  # noqa: E402


# One client (and one event loop) for the whole test run, so the database pool is reused safely.
@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
