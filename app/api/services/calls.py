from collections import defaultdict

from fastapi import HTTPException, WebSocket
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.api.schemas.auth import CurrentAccount

CALL_SQL = text("""
    SELECT call_id, account_id, customer_id, booking_id, status, assigned_staff_id, ended_at
    FROM calls WHERE call_id = :call_id
    FOR UPDATE
""")
# queries.sql 14: messages are numbered 1, 2, 3... within a call (the call row is locked, so two never get the same number)
ADD_MESSAGE_SQL = text("""
    INSERT INTO call_messages (call_id, turn_no, role, content, latency_ms)
    VALUES (:call_id, (SELECT coalesce(max(turn_no), 0) + 1 FROM call_messages WHERE call_id = :call_id),
            :role, :content, :latency_ms)
    RETURNING turn_no, created_at
""")


async def call_for(db: AsyncConnection, call_id, account: CurrentAccount | None, writing: bool = True,
                   check_owner: bool = True):
    """The call, locked until commit. A guest's call is written to only with that guest's login (or by staff);
    a visitor's call only needs its id, which nobody can guess."""
    call = (await db.execute(CALL_SQL, {"call_id": str(call_id)})).mappings().first()
    if call is None:
        raise HTTPException(status_code=404, detail={"reason": "CALL_NOT_FOUND"})
    is_staff = account is not None and account.role in ("Staff", "Admin")
    if check_owner and call["account_id"] and not is_staff and (account is None or account.account_id != call["account_id"]):
        raise HTTPException(status_code=403, detail={"reason": "NOT_YOUR_CALL"})
    if writing and call["ended_at"]:
        raise HTTPException(status_code=409, detail={"reason": "CALL_ENDED"})
    return call


async def add_message(db: AsyncConnection, call_id, role: str, content: str, latency_ms: int | None = None):
    """Call call_for() first in the same transaction: it locks the call so the turn numbers stay in order."""
    return (await db.execute(ADD_MESSAGE_SQL, {"call_id": str(call_id), "role": role, "content": content,
                                               "latency_ms": latency_ms})).mappings().one()


class ChatHub:
    """Who is connected right now: staff dashboards and guests in a live chat.
    It lives in the server's memory, which is enough for one server process; several processes would share
    it through Redis (deployment)."""

    def __init__(self):
        self.staff: dict[int, set[WebSocket]] = defaultdict(set)
        self.guests: dict[str, set[WebSocket]] = defaultdict(set)

    def online_staff(self) -> list[int]:
        return [account_id for account_id, sockets in self.staff.items() if sockets]

    @staticmethod
    async def _send(sockets: set[WebSocket], payload: dict) -> None:
        for socket in list(sockets):
            try:
                await socket.send_json(payload)
            except Exception:          # the page was closed: forget that connection
                sockets.discard(socket)

    async def to_staff(self, account_id: int, payload: dict) -> None:
        await self._send(self.staff[account_id], payload)

    async def to_guest(self, call_id, payload: dict) -> None:
        await self._send(self.guests[str(call_id)], payload)


hub = ChatHub()
