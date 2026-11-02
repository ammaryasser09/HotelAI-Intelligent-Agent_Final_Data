from app.api.config import settings
from app.api.main import app

FIRST_SEVEN = "/health,/,/availability,/room-types,/hotel-photos,/menu,/discount-codes/{code}"


def test_docs_can_show_only_some_endpoints(client, monkeypatch):
    monkeypatch.setattr(settings, "docs_only", FIRST_SEVEN)
    monkeypatch.setattr(app, "openapi_schema", None)          # build the page description again
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths) == set(FIRST_SEVEN.split(","))
    assert client.post("/auth/login", json={"email": "x@example.com", "password": "x"}).status_code == 401   # still works

    monkeypatch.setattr(settings, "docs_only", "")
    monkeypatch.setattr(app, "openapi_schema", None)
    assert len(client.get("/openapi.json").json()["paths"]) > 40      # everything again
    app.openapi_schema = None
