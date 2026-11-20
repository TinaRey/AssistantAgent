from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=100)


TraceStatus = Literal["ok", "error", "timeout", "invalid_input", "unknown_tool", "pending_approval"]


class ToolTrace(BaseModel):
    id: str
    call_id: str
    tool: str
    status: TraceStatus
    started_at: datetime
    duration_ms: int
    arguments: dict[str, Any] | None = None
    error: str | None = None


class PendingAction(BaseModel):
    id: str
    tool: str
    arguments: dict[str, Any]
    status: Literal["pending", "approved", "rejected", "failed"] = "pending"
    created_at: datetime
    result: dict[str, Any] | None = None
    error: str | None = None


class Artifact(BaseModel):
    """Structured tool output the UI renders as an editable preview."""

    call_id: str
    tool: str
    data: dict[str, Any]


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[ToolTrace] = []
    pending_actions: list[PendingAction] = []
    artifacts: list[Artifact] = []
    iteration_limit_reached: bool = False
