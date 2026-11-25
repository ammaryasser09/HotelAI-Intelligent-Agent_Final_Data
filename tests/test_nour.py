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
