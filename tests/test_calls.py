import pytest
from sqlalchemy import text
from starlette.websockets import WebSocketDisconnect

from tests.test_auth import bearer
from tests.test_bookings import database, token  # noqa: F401  (pytest fixture: Paul's login)
from tests.test_staff import admin_token, staff_token  # noqa: F401


@pytest.fixture
def calls():
    """Calls the test starts are deleted afterwards, with their messages, actions and tickets."""
    ids = []
    yield ids
    engine = database()
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM customer_requests WHERE call_id = ANY(CAST(:ids AS uuid[]))"), {"ids": ids})
        connection.execute(text("DELETE FROM calls WHERE call_id = ANY(CAST(:ids AS uuid[]))"), {"ids": ids})
    engine.dispose()


def start(client, calls, token=None, **body):
    headers = bearer(token) if token else {}
    response = client.post("/calls", headers=headers, json=body)
    assert response.status_code == 201, response.text
    calls.append(response.json()["call_id"])
    return response.json()["call_id"]


def test_a_call_is_logged_for_the_dashboard(client, token, staff_token, admin_token, calls):
    call_id = start(client, calls, token, channel="voice", language="English")
    for role, content in [("guest", "Is a Double free next weekend?"), ("agent", "Yes, room 401 with a Nile view.")]:
        saved = client.post(f"/calls/{call_id}/messages", headers=bearer(token),
                            json={"role": role, "content": content, "latency_ms": 900 if role == "agent" else None})
        assert saved.status_code == 201, saved.text
    assert saved.json()["turn_no"] == 2
    action = client.post(f"/calls/{call_id}/actions", headers=bearer(token), json={
        "tool_name": "check_availability", "arguments": {"room_type": "Double"}, "result": {"free": [401]}})
    assert action.status_code == 201, action.text
    ended = client.post(f"/calls/{call_id}/end", headers=bearer(token), json={"summary": "Asked about a Double"})
    assert ended.json()["status"] == "completed"
    late = client.post(f"/calls/{call_id}/messages", headers=bearer(token), json={"role": "guest", "content": "hi"})
    assert late.status_code == 409 and late.json()["detail"]["reason"] == "CALL_ENDED"

    detail = client.get(f"/staff/calls/{call_id}", headers=bearer(staff_token)).json()
    assert [m["role"] for m in detail["messages"]] == ["guest", "agent"]
    assert detail["call_actions"][0]["arguments"] == {"room_type": "Double"}
    assert (detail["guest_name"], detail["avg_latency_ms"], detail["summary"]) == ("Paul Fischer", 900, "Asked about a Double")
    assert call_id in [c["call_id"] for c in client.get("/admin/calls", headers=bearer(admin_token)).json()]


def test_only_the_guest_writes_to_their_call(client, token, calls):
    call_id = start(client, calls, token)
    visitor = client.post(f"/calls/{call_id}/messages", json={"role": "guest", "content": "hello"})
    assert visitor.status_code == 403 and visitor.json()["detail"]["reason"] == "NOT_YOUR_CALL"
    anonymous_call = start(client, calls)                          # a visitor's call needs only its id
    assert client.post(f"/calls/{anonymous_call}/messages", json={"role": "guest", "content": "hello"}).status_code == 201


def test_nobody_online_means_a_callback_ticket(client, token, calls):
    call_id = start(client, calls, token)
    handed = client.post(f"/calls/{call_id}/handoff", headers=bearer(token), json={"reason": "Billing problem"})
    assert handed.status_code == 200, handed.text
    assert handed.json()["mode"] == "callback" and handed.json()["request_id"].startswith("REQ")
    ticket = {r["request_id"]: r for r in client.get("/me/requests", headers=bearer(token)).json()}[handed.json()["request_id"]]
    assert (ticket["request_type"], ticket["priority"]) == ("Staff Callback", "Urgent")


def test_live_chat_between_the_guest_and_staff(client, token, staff_token, calls):
    call_id = start(client, calls, token)
    with client.websocket_connect(f"/ws/staff?token={staff_token}") as staff:
        handed = client.post(f"/calls/{call_id}/handoff", headers=bearer(token), json={"reason": "Wants a person"})
        assert handed.json()["mode"] == "live_chat" and handed.json()["staff_name"] == "Karim"
        assert staff.receive_json() == {"type": "handoff", "call_id": call_id, "reason": "Wants a person"}

        with client.websocket_connect(f"/ws/calls/{call_id}?token={handed.json()['chat_token']}") as guest:
            guest.send_json({"text": "My card was charged twice"})
            assert guest.receive_json()["content"] == "My card was charged twice"     # the guest sees their own line
            assert staff.receive_json()["role"] == "guest"

            staff.send_json({"call_id": call_id, "text": "Sorry about that, I am checking now"})
            assert staff.receive_json()["role"] == "staff"
            assert guest.receive_json()["content"] == "Sorry about that, I am checking now"

            staff.send_json({"call_id": call_id, "type": "end"})
            assert guest.receive_json() == {"type": "ended", "call_id": call_id}

    detail = client.get(f"/staff/calls/{call_id}", headers=bearer(staff_token)).json()
    assert [m["role"] for m in detail["messages"]] == ["system", "guest", "staff"]
    assert detail["status"] == "escalated" and detail["assigned_to"] == "Karim Fathy"


def test_chat_doors_stay_closed_without_the_right_token(client, token, calls):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/staff?token={token}") as socket:      # a guest is not staff
            socket.receive_json()
    call_id = start(client, calls, token)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/calls/{call_id}?token=made-up") as socket:
            socket.receive_json()
