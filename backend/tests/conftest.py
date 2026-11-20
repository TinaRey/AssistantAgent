from pathlib import Path
from typing import Any

import pytest

from app.integrations.llm import AssistantTurn, ToolCall
from app.integrations.search import SearchResult
from app.schemas.chat import ChatMessage
from app.services.orchestrator import Orchestrator
from app.services.tool_runner import ApprovalStore, ToolRunner
from app.services.tracing import Tracer
from app.tools.base import ToolContext
from app.tools.registry import build_registry


class FakeLLM:
    """chat() replays scripted turns; structured() returns scripted model instances."""

    def __init__(
        self, turns: list[AssistantTurn] | None = None, structured: list[Any] | None = None
    ):
        self.turns = list(turns or [])
        self.structured_out = list(structured or [])
        self.chat_calls = 0
        self.structured_messages: list[Any] = []

    async def chat(self, messages, tools):  # type: ignore[no-untyped-def]
        self.chat_calls += 1
        return self.turns.pop(0) if self.turns else self.turns_repeat()

    def turns_repeat(self) -> AssistantTurn:
        return AssistantTurn(
            tool_calls=[ToolCall(id="x", name="retrieve_knowledge", arguments='{"query": "loop"}')]
        )

    async def structured(self, messages, schema):  # type: ignore[no-untyped-def]
        self.structured_messages.append(messages)
        return self.structured_out.pop(0)


class FakeSearch:
    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        return self.results


class FakeKnowledge:
    async def search(self, query, top_k):  # type: ignore[no-untyped-def]
        return []


def call(name: str, args: str, id: str = "c1") -> AssistantTurn:
    return AssistantTurn(tool_calls=[ToolCall(id=id, name=name, arguments=args)])


@pytest.fixture
def make_runtime(tmp_path: Path):  # type: ignore[no-untyped-def]
    def _make(llm: FakeLLM, search: FakeSearch | None = None, max_iter: int = 4, registry=None):
        ctx = ToolContext(
            llm=llm,
            search=search or FakeSearch([]),
            knowledge=FakeKnowledge(),
            storage_dir=tmp_path,
        )
        tracer = Tracer()
        runner = ToolRunner(registry or build_registry(), ctx, tracer, ApprovalStore())
        return Orchestrator(llm, runner, max_iter), runner, tracer, ctx

    return _make


def user(text: str) -> list[ChatMessage]:
    return [ChatMessage(role="user", content=text)]
