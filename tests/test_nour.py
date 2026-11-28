import asyncio

import pytest
from starlette.websockets import WebSocketDisconnect


def test_nour_refuses_a_made_up_token(client):
    with pytest.raises(WebSocketDisconnect) as closed:
        with client.websocket_connect("/ws/nour?token=made-up") as socket:
            socket.receive_json()
    assert closed.value.code == 4401


def test_nour_test_page_is_only_there_in_dev_mode(client, monkeypatch):
    monkeypatch.delenv("NOUR_DEV", raising=False)
    assert client.get("/nour/test").status_code == 404
    monkeypatch.setenv("NOUR_DEV", "1")
    page = client.get("/nour/test")
    assert page.status_code == 200 and "/ws/nour" in page.text


def test_nour_turns_away_visitors_over_the_limit(client, monkeypatch):
    monkeypatch.setenv("NOUR_VISITOR_CALLS", "0")
    with client.websocket_connect("/ws/nour") as socket:
        closed = socket.receive_json()
    assert closed == {"type": "closed", "reason": "TOO_MANY_VISITOR_CALLS",
                      "advice": "try again in a few minutes or log in"}


def test_nour_ends_a_visitor_call_at_the_time_limit(client, monkeypatch):
    from app.api.routers import nour

    async def long_call(websocket, account_id):
        await websocket.send_json({"type": "ready"})
        await asyncio.sleep(30)

    monkeypatch.setattr(nour, "call_nour", long_call)
    monkeypatch.setenv("NOUR_VISITOR_MINUTES", "0.02")
    with client.websocket_connect("/ws/nour") as socket:
        assert socket.receive_json() == {"type": "ready"}
        closed = socket.receive_json()
    assert closed["reason"] == "VISITOR_TIME_LIMIT"
