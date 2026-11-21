"""Executes tools safely: validation, timeout, error containment, tracing, approval gate."""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, ValidationError

from app.integrations.llm import LLMError, ToolCall
from app.schemas.chat import PendingAction, ToolTrace
from app.services.tracing import Tracer
from app.tools.base import ToolContext, ToolError, ToolSpec

logger = logging.getLogger(__name__)

CARD_NOTE = (
    "Ce résultat est DÉJÀ affiché à l'utilisatrice sous forme de fiche modifiable. Ne le recopie "
    "pas : réponds en 2 à 4 phrases (points clés, limites) et propose une prochaine étape."
)


@dataclass
class ToolOutcome:
    content: str  # what the model sees
    trace: ToolTrace
    pending: PendingAction | None = None
    output: dict | None = None


class ApprovalStore:
    def __init__(self) -> None:
        self._actions: dict[str, PendingAction] = {}

    def create(self, tool: str, arguments: dict) -> PendingAction:
        action = PendingAction(
            id=uuid.uuid4().hex, tool=tool, arguments=arguments, created_at=datetime.now(UTC)
        )
        self._actions[action.id] = action
        return action

    def get(self, action_id: str) -> PendingAction | None:
        return self._actions.get(action_id)

    def list(self) -> list[PendingAction]:
        return sorted(self._actions.values(), key=lambda a: a.created_at, reverse=True)


class ToolRunner:
    def __init__(
        self,
        registry: dict[str, ToolSpec],
        ctx: ToolContext,
        tracer: Tracer,
        approvals: ApprovalStore,
    ) -> None:
        self.registry, self.ctx, self.tracer, self.approvals = registry, ctx, tracer, approvals

    async def run(self, call: ToolCall) -> ToolOutcome:
        started = datetime.now(UTC)
        spec = self.registry.get(call.name)
        if spec is None:
            return self._fail(call, started, "unknown_tool", f"Unknown tool '{call.name}'.", None)

        try:
            args = json.loads(call.arguments or "{}")
            inp = spec.input_model.model_validate(args)
        except (json.JSONDecodeError, ValidationError) as exc:
            msg = f"Invalid arguments: {_short(exc)}. Fix them and retry."
            return self._fail(call, started, "invalid_input", msg, None)

        dumped = inp.model_dump(mode="json")
        if spec.requires_approval:
            action = self.approvals.create(spec.name, dumped)
            trace = self.tracer.record(
                call_id=call.id,
                tool=spec.name,
                status="pending_approval",
                started_at=started,
                arguments=dumped,
            )
            content = (
                "Action NOT executed: it requires human approval. Tell the user it is "
                "waiting for their confirmation."
            )
            return ToolOutcome(content, trace, action)

        try:
            output = await self._execute(spec, inp)
        except TimeoutError:
            return self._fail(call, started, "timeout", f"'{spec.name}' timed out.", dumped)
        except (ToolError, LLMError) as exc:
            return self._fail(call, started, "error", str(exc), dumped)
        except Exception:
            logger.exception("Unexpected failure in tool %s", spec.name)
            return self._fail(call, started, "error", f"'{spec.name}' failed unexpectedly.", dumped)

        trace = self.tracer.record(
            call_id=call.id, tool=spec.name, status="ok", started_at=started, arguments=dumped
        )
        dumped_out = output.model_dump(mode="json")
        content = (
            json.dumps({"result": dumped_out, "note": CARD_NOTE}, ensure_ascii=False)
            if spec.ui_card
            else output.model_dump_json()
        )
        return ToolOutcome(content, trace, output=dumped_out)

    async def approve(self, action_id: str) -> PendingAction:
        """Human-approved execution of a stored action. Runs at most once."""
        action = self.approvals.get(action_id)
        if action is None:
            raise KeyError(action_id)
        if action.status != "pending":
            return action
        action.status = "approved"  # claim first: prevents double execution
        spec = self.registry[action.tool]
        started = datetime.now(UTC)
        try:
            output = await self._execute(spec, spec.input_model.model_validate(action.arguments))
            action.result = output.model_dump(mode="json")
            status, error = "ok", None
        except Exception as exc:  # noqa: BLE001
            action.status, action.error = "failed", _short(exc) or "failed"
            status, error = "error", action.error
        self.tracer.record(
            call_id=action.id,
            tool=action.tool,
            status=status,
            started_at=started,  # type: ignore[arg-type]
            arguments=action.arguments,
            error=error,
        )
        return action

    def reject(self, action_id: str) -> PendingAction:
        action = self.approvals.get(action_id)
        if action is None:
            raise KeyError(action_id)
        if action.status == "pending":
            action.status = "rejected"
        return action

    async def _execute(self, spec: ToolSpec, inp: BaseModel) -> BaseModel:
        return await asyncio.wait_for(spec.func(inp, self.ctx), timeout=spec.timeout_s)

    def _fail(self, call: ToolCall, started: datetime, status, message: str, args) -> ToolOutcome:
        trace = self.tracer.record(
            call_id=call.id,
            tool=call.name,
            status=status,
            started_at=started,
            arguments=args,
            error=message,
        )
        return ToolOutcome(json.dumps({"error": message}), trace)


def _short(exc: Exception) -> str:
    return str(exc).replace("\n", " ")[:300]
