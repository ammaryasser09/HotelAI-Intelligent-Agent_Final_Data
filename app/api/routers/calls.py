import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.db import engine, get_db
from app.api.schemas.auth import CurrentAccount
from app.api.schemas.calls import (CallDetail, CallOverview, CallStarted, EndCall, HandoffRequest, HandoffResult,
                                   MessageSaved, NewAction, NewMessage, StartCall)
from app.api.security import (create_chat_token, get_current_admin, get_current_staff, get_optional_account,
                              read_access_token, read_chat_token)
from app.api.services.calls import add_message, call_for, hub

router = APIRouter(tags=["Calls & live chat"])

# ---------- logging a call (queries.sql 14) ----------

START_SQL = text("""
    INSERT INTO calls (channel, language, account_id, customer_id)
    VALUES (:channel, :language, :account_id, (SELECT customer_id FROM user_accounts WHERE account_id = :account_id))
    RETURNING call_id, status
""")
ACTION_SQL = text("""
    INSERT INTO call_actions (call_id, tool_name, arguments, result, success, booking_id)
    VALUES (:call_id, :tool_name, CAST(:arguments AS jsonb), CAST(:result AS jsonb), :success, upper(:booking_id))
""")
BOOKING_EXISTS_SQL = text("SELECT 1 FROM bookings WHERE booking_id = upper(:booking_id)")
END_SQL = text("""
    UPDATE calls SET status = CASE WHEN status = 'active' THEN 'completed' ELSE status END,
                     ended_at = now(), summary = coalesce(:summary, summary)
    WHERE call_id = :call_id
""")


@router.post("/calls", response_model=CallStarted, status_code=201)
async def start_call(body: StartCall, account: CurrentAccount | None = Depends(get_optional_account),
                     db: AsyncConnection = Depends(get_db)):
    """A conversation with Nour starts (a logged-in guest or a visitor). Its id is used for everything after."""
    row = (await db.execute(START_SQL, {**body.model_dump(),
                                        "account_id": account.account_id if account else None})).mappings().one()
    await db.commit()
    return CallStarted(**row)


@router.post("/calls/{call_id}/messages", response_model=MessageSaved, status_code=201)
async def log_message(call_id: str, body: NewMessage, account: CurrentAccount | None = Depends(get_optional_account),
                      db: AsyncConnection = Depends(get_db)):
    await call_for(db, call_id, account)
    saved = await add_message(db, call_id, body.role, body.content, body.latency_ms)
    await db.commit()
    return MessageSaved(**saved)


@router.post("/calls/{call_id}/actions", status_code=201)
async def log_action(call_id: str, body: NewAction, account: CurrentAccount | None = Depends(get_optional_account),
                     db: AsyncConnection = Depends(get_db)):
    await call_for(db, call_id, account)
    if body.booking_id and not (await db.execute(BOOKING_EXISTS_SQL, {"booking_id": body.booking_id})).first():
        raise HTTPException(status_code=404, detail={"reason": "BOOKING_NOT_FOUND"})
    await db.execute(ACTION_SQL, {"call_id": call_id, "tool_name": body.tool_name, "success": body.success,
                                  "arguments": json.dumps(body.arguments, ensure_ascii=False),
                                  "result": None if body.result is None else json.dumps(body.result, ensure_ascii=False),
                                  "booking_id": body.booking_id})
    await db.commit()
    return {"saved": True}


@router.post("/calls/{call_id}/end", response_model=CallStarted)
async def end_call(call_id: str, body: EndCall, account: CurrentAccount | None = Depends(get_optional_account),
                   db: AsyncConnection = Depends(get_db)):
    call = await call_for(db, call_id, account)
    await db.execute(END_SQL, {"call_id": call_id, "summary": body.summary})
    await db.commit()
    if call["assigned_staff_id"]:
        await hub.to_staff(call["assigned_staff_id"], {"type": "ended", "call_id": call_id})
    return CallStarted(call_id=call_id, status="completed" if call["status"] == "active" else call["status"])


# ---------- handoff to a person (queries.sql 10c) ----------

# the free staff member: online now, fewest live chats going on
FREE_STAFF_SQL = text("""
    SELECT a.account_id, a.full_name,
           (SELECT count(*) FROM calls c WHERE c.assigned_staff_id = a.account_id
                                          AND c.status = 'escalated' AND c.ended_at IS NULL) AS chats
    FROM user_accounts a
    WHERE a.account_id = ANY(:online) AND a.role IN ('Staff', 'Admin') AND a.is_active
    ORDER BY chats, a.account_id LIMIT 1
""")
ESCALATE_SQL = text("""
    UPDATE calls SET status = 'escalated', escalation_reason = :reason, assigned_staff_id = :staff_id
    WHERE call_id = :call_id
""")
CALLBACK_TICKET_SQL = text("""
    INSERT INTO customer_requests (customer_id, booking_id, call_id, request_type, request_text, priority)
    VALUES (:customer_id, :booking_id, :call_id, 'Staff Callback', :reason, 'Urgent')
    RETURNING request_id
""")


@router.post("/calls/{call_id}/handoff", response_model=HandoffResult)
async def handoff(call_id: str, body: HandoffRequest, account: CurrentAccount | None = Depends(get_optional_account),
                  db: AsyncConnection = Depends(get_db)):
    """The guest has a problem and asks for a person. A free member of staff on the dashboard takes it as a
    live chat; when nobody is free, an urgent Staff Callback ticket is opened instead."""
    call = await call_for(db, call_id, account)
    if call["assigned_staff_id"]:
        raise HTTPException(status_code=409, detail={"reason": "ALREADY_HANDED_OVER"})
    staff = (await db.execute(FREE_STAFF_SQL, {"online": hub.online_staff()})).mappings().first()
    await db.execute(ESCALATE_SQL, {"call_id": call_id, "reason": body.reason,
                                    "staff_id": staff["account_id"] if staff else None})

    if staff is None:
        request_id = (await db.execute(CALLBACK_TICKET_SQL, {
            "customer_id": call["customer_id"], "booking_id": call["booking_id"], "call_id": call_id,
            "reason": body.reason})).scalar_one()
        await add_message(db, call_id, "system", f"Nobody free: Staff Callback ticket {request_id} opened")
        await db.commit()
        return HandoffResult(mode="callback", request_id=request_id)

    first_name = staff["full_name"].split()[0]
    await add_message(db, call_id, "system", f"Handed over to {staff['full_name']} (live chat)")
    await db.commit()
    await hub.to_staff(staff["account_id"], {"type": "handoff", "call_id": call_id, "reason": body.reason})
    return HandoffResult(mode="live_chat", staff_name=first_name, chat_token=create_chat_token(call_id))


# ---------- the dashboard: calls to review, chats going on ----------

OVERVIEW_COLUMNS = """call_id, started_at, ended_at, channel, language, status, escalation_reason, visitor, guest_name,
                      booking_id, assigned_to, turns, actions, tickets, avg_latency_ms, duration_seconds"""
CALLS_SQL = text(f"""
    SELECT {OVERVIEW_COLUMNS} FROM v_call_overview
    WHERE CAST(:status AS text) IS NULL OR status = CAST(:status AS text)
    ORDER BY started_at DESC LIMIT :limit
""")
MY_CHATS_SQL = text(f"""
    SELECT {OVERVIEW_COLUMNS} FROM v_call_overview v
    WHERE v.status = 'escalated' AND v.ended_at IS NULL
      AND v.call_id IN (SELECT call_id FROM calls WHERE assigned_staff_id = :account_id)
    ORDER BY started_at
""")
DETAIL_SQL = text(f"""
    SELECT {OVERVIEW_COLUMNS}, (SELECT summary FROM calls c WHERE c.call_id = v.call_id) AS summary
    FROM v_call_overview v WHERE call_id = :call_id
""")
MESSAGES_SQL = text("""
    SELECT turn_no, role, content, latency_ms, created_at FROM call_messages WHERE call_id = :call_id ORDER BY turn_no
""")
ACTIONS_SQL = text("""
    SELECT tool_name, arguments, result, success, booking_id, created_at FROM call_actions
    WHERE call_id = :call_id ORDER BY created_at
""")


@router.get("/admin/calls", response_model=list[CallOverview])
async def calls(status: Literal["active", "completed", "escalated", "abandoned"] | None = None,
                limit: int = Query(default=50, ge=1, le=500),
                admin: CurrentAccount = Depends(get_current_admin), db: AsyncConnection = Depends(get_db)):
    """Nour's calls, newest first: turns, tools used, tickets, answer speed, handoffs."""
    rows = (await db.execute(CALLS_SQL, {"status": status, "limit": limit})).mappings().all()
    return [CallOverview(**row) for row in rows]


@router.get("/staff/chats", response_model=list[CallOverview])
async def my_chats(staff: CurrentAccount = Depends(get_current_staff), db: AsyncConnection = Depends(get_db)):
    """The live chats handed to me that are still going on (to show them again after a page reload)."""
    rows = (await db.execute(MY_CHATS_SQL, {"account_id": staff.account_id})).mappings().all()
    return [CallOverview(**row) for row in rows]


@router.get("/staff/calls/{call_id}", response_model=CallDetail)
async def call_detail(call_id: str, staff: CurrentAccount = Depends(get_current_staff),
                      db: AsyncConnection = Depends(get_db)):
    """Everything said and done in a call: what the member of staff reads before answering a chat."""
    row = (await db.execute(DETAIL_SQL, {"call_id": call_id})).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail={"reason": "CALL_NOT_FOUND"})
    messages = (await db.execute(MESSAGES_SQL, {"call_id": call_id})).mappings().all()
    actions = (await db.execute(ACTIONS_SQL, {"call_id": call_id})).mappings().all()
    return CallDetail(**row, messages=[dict(m) for m in messages], call_actions=[dict(a) for a in actions])


# ---------- the live chat itself (WebSocket) ----------
# A browser cannot add headers to a WebSocket, so the token comes in the address: ?token=...
# Messages are JSON: {"text": "..."} from the guest, {"call_id": "...", "text": "..."} from staff,
# {"call_id": "...", "type": "end"} when staff close the chat.

def message_payload(call_id, role: str, content: str, saved) -> dict:
    return {"type": "message", "call_id": str(call_id), "role": role, "content": content,
            "turn_no": saved["turn_no"], "created_at": saved["created_at"].isoformat()}


async def read_json(websocket: WebSocket) -> dict | None:
    try:
        data = json.loads(await websocket.receive_text())
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


@router.websocket("/ws/staff")
async def staff_socket(websocket: WebSocket, token: str = ""):
    """The dashboard of a member of staff: receives handoffs and guest messages, sends answers."""
    try:
        account = read_access_token(token)
    except HTTPException:
        await websocket.close(code=4401)
        return
    if account.role not in ("Staff", "Admin"):
        await websocket.close(code=4403)
        return
    await websocket.accept()
    hub.staff[account.account_id].add(websocket)
    try:
        while True:
            data = await read_json(websocket)
            if data is None or not data.get("call_id"):
                await websocket.send_json({"type": "error", "reason": "BAD_MESSAGE"})
                continue
            call_id = str(data["call_id"])
            async with engine.connect() as db:
                try:
                    call = await call_for(db, call_id, account)
                except HTTPException as refused:
                    await websocket.send_json({"type": "error", "reason": refused.detail["reason"], "call_id": call_id})
                    continue
                if call["assigned_staff_id"] != account.account_id:
                    await websocket.send_json({"type": "error", "reason": "NOT_YOUR_CHAT", "call_id": call_id})
                    continue
                if data.get("type") == "end":
                    await db.execute(END_SQL, {"call_id": call_id, "summary": "Live chat closed by staff"})
                    await db.commit()
                    await hub.to_guest(call_id, {"type": "ended", "call_id": call_id})
                    await websocket.send_json({"type": "ended", "call_id": call_id})
                    continue
                content = str(data.get("text", "")).strip()[:5000]
                if not content:
                    await websocket.send_json({"type": "error", "reason": "EMPTY_MESSAGE", "call_id": call_id})
                    continue
                saved = await add_message(db, call_id, "staff", content)
                await db.commit()
            payload = message_payload(call_id, "staff", content, saved)
            await hub.to_guest(call_id, payload)
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        pass
    finally:
        hub.staff[account.account_id].discard(websocket)


@router.websocket("/ws/calls/{call_id}")
async def guest_socket(websocket: WebSocket, call_id: str, token: str = ""):
    """The guest's side of a live chat, opened with the chat_token the handoff answered with."""
    if read_chat_token(token) != call_id:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    hub.guests[call_id].add(websocket)
    try:
        while True:
            data = await read_json(websocket)
            content = str((data or {}).get("text", "")).strip()[:5000]
            if not content:
                await websocket.send_json({"type": "error", "reason": "EMPTY_MESSAGE"})
                continue
            async with engine.connect() as db:
                try:
                    call = await call_for(db, call_id, None, check_owner=False)   # the chat token was the check
                except HTTPException as refused:
                    await websocket.send_json({"type": "error", "reason": refused.detail["reason"]})
                    continue
                saved = await add_message(db, call_id, "guest", content)
                await db.commit()
            payload = message_payload(call_id, "guest", content, saved)
            if call["assigned_staff_id"]:
                await hub.to_staff(call["assigned_staff_id"], payload)
            await websocket.send_json(payload)
    except WebSocketDisconnect:
        pass
    finally:
        hub.guests[call_id].discard(websocket)
