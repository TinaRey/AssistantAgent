"""Orchestration only: talks to the LLM and delegates every tool call to the ToolRunner."""

import logging
from typing import Any

from app.integrations.llm import LLMClient
from app.schemas.chat import Artifact, ChatMessage, ChatResponse, PendingAction, ToolTrace
from app.services.prompts import SYSTEM_PROMPT
from app.services.tool_runner import ToolRunner

logger = logging.getLogger(__name__)

LIMIT_MESSAGE = (
    "I could not finish within the allowed number of steps. Here is where things stand; "
    "please narrow the request or ask me to continue."
)


class Orchestrator:
    def __init__(self, llm: LLMClient, runner: ToolRunner, max_iterations: int) -> None:
        self.llm, self.runner, self.max_iterations = llm, runner, max_iterations

    async def run(self, messages: list[ChatMessage]) -> ChatResponse:
        convo: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        convo += [m.model_dump() for m in messages]
        tools = [s.openai_schema() for s in self.runner.registry.values()]
        traces: list[ToolTrace] = []
        pending: list[PendingAction] = []
        artifacts: list[Artifact] = []

        for _ in range(self.max_iterations):  # hard cap: no infinite tool loops
            turn = await self.llm.chat(convo, tools)
            if not turn.tool_calls:
                return ChatResponse(
                    reply=turn.content or "",
                    tool_calls=traces,
                    pending_actions=pending,
                    artifacts=artifacts,
                )

            convo.append(
                {
                    "role": "assistant",
                    "content": turn.content,
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": c.arguments},
                        }
                        for c in turn.tool_calls
                    ],
                }
            )
            for call in turn.tool_calls:
                outcome = await self.runner.run(call)
                traces.append(outcome.trace)
                if outcome.output is not None:
                    artifacts.append(Artifact(call_id=call.id, tool=call.name, data=outcome.output))
                if outcome.pending:
                    pending.append(outcome.pending)
                convo.append({"role": "tool", "tool_call_id": call.id, "content": outcome.content})

        logger.warning("Tool loop hit the iteration cap (%d)", self.max_iterations)
        return ChatResponse(
            reply=LIMIT_MESSAGE,
            tool_calls=traces,
            pending_actions=pending,
            artifacts=artifacts,
            iteration_limit_reached=True,
        )
