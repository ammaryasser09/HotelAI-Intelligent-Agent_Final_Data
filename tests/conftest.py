import pytest
from fastapi.testclient import TestClient

from app.api.main import app


# One client (and one event loop) for the whole test run, so the database pool is reused safely.
@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
