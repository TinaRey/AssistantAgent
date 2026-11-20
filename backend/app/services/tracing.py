import logging
import uuid
from collections import deque
from datetime import UTC, datetime
from typing import Any

from app.schemas.chat import ToolTrace, TraceStatus

logger = logging.getLogger("tools")


class Tracer:
    """Keeps a bounded history of tool calls. Logs never contain arguments or outputs."""

    def __init__(self, maxlen: int = 500) -> None:
        self._history: deque[ToolTrace] = deque(maxlen=maxlen)

    def record(
        self,
        *,
        call_id: str,
        tool: str,
        status: TraceStatus,
        started_at: datetime,
        arguments: dict[str, Any] | None,
        error: str | None = None,
    ) -> ToolTrace:
        duration = int((datetime.now(UTC) - started_at).total_seconds() * 1000)
        trace = ToolTrace(
            id=uuid.uuid4().hex,
            call_id=call_id,
            tool=tool,
            status=status,
            started_at=started_at,
            duration_ms=duration,
            arguments=arguments,
            error=error,
        )
        self._history.append(trace)
        logger.info("tool=%s status=%s duration_ms=%d", tool, status, duration)
        return trace

    def recent(self, limit: int = 100) -> list[ToolTrace]:
        return list(self._history)[-limit:][::-1]
