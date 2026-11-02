from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

Language = Literal["Arabic-Egyptian", "Arabic", "English", "French", "Russian"]


class StartCall(BaseModel):
    channel: Literal["voice", "text"] = "voice"
    language: Language | None = None


class CallStarted(BaseModel):
    call_id: UUID
    status: str


class NewMessage(BaseModel):
    role: Literal["guest", "agent", "system"]          # staff write through the live chat
    content: str = Field(min_length=1, max_length=5000)
    latency_ms: int | None = Field(default=None, ge=0)  # how long Nour took to answer


class MessageSaved(BaseModel):
    turn_no: int
    created_at: datetime


class NewAction(BaseModel):
    """A tool Nour used during the call (check_availability, create_booking...), for the dashboard."""
    tool_name: str = Field(min_length=1, max_length=40, examples=["check_availability"])
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | list[Any] | None = None
    success: bool = True
    booking_id: str | None = Field(default=None, pattern=r"^[Bb]\d{6}$")


class EndCall(BaseModel):
    summary: str | None = Field(default=None, max_length=2000)


class HandoffRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500, examples=["The guest wants to speak to a person about a billing problem"])


class HandoffResult(BaseModel):
    mode: Literal["live_chat", "callback"]
    staff_name: str | None = None      # live chat: who is answering
    chat_token: str | None = None      # live chat: opens /ws/calls/{call_id}?token=...
    request_id: str | None = None      # callback: the Staff Callback ticket


class CallOverview(BaseModel):
    call_id: UUID
    started_at: datetime
    ended_at: datetime | None
    channel: str
    language: str | None
    status: str
    escalation_reason: str | None
    visitor: bool
    guest_name: str | None
    booking_id: str | None
    assigned_to: str | None
    turns: int
    actions: int
    tickets: int
    avg_latency_ms: float | None
    duration_seconds: int | None


class CallMessage(BaseModel):
    turn_no: int
    role: str
    content: str
    latency_ms: int | None
    created_at: datetime


class CallAction(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    result: Any
    success: bool
    booking_id: str | None
    created_at: datetime


class CallDetail(CallOverview):
    summary: str | None
    messages: list[CallMessage]
    call_actions: list[CallAction]
