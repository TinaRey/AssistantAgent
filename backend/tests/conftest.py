import hashlib
import math
import os
import re
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db.base import Base, make_engine, make_session_factory
from app.integrations.llm import AssistantTurn, ToolCall
from app.integrations.search import SearchResult
from app.knowledge_base.service import KnowledgeService
from app.models.document import EMBEDDING_DIM
from app.schemas.chat import ChatMessage
from app.services.orchestrator import Orchestrator
from app.services.presentations import MemoryPresentationStore, PgPresentationStore
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


def tiny_png(color: tuple[int, int, int] = (40, 140, 90)) -> bytes:
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(out, "PNG")
    return out.getvalue()


class FakeImages:
    """Counts calls so tests can prove that nothing is generated (= billed) unless asked."""

    def __init__(self, fail_with: Exception | None = None) -> None:
        self.prompts: list[str] = []
        self.fail_with = fail_with

    async def generate(self, prompt: str) -> bytes:
        self.prompts.append(prompt)
        if self.fail_with:
            raise self.fail_with
        return tiny_png()


class FakeTemplates:
    """Template PDFs by file name."""

    def __init__(self, pdfs: dict[str, bytes] | None = None) -> None:
        self.pdfs = pdfs or {}

    async def list_pdf_names(self) -> list[str]:
        return list(self.pdfs)

    async def get_pdf(self, filename: str):  # type: ignore[no-untyped-def]
        from app.integrations.templates import TemplatePdf

        return TemplatePdf(filename, self.pdfs[filename]) if filename in self.pdfs else None


class FakeKnowledge:
    async def search(self, query, top_k):  # type: ignore[no-untyped-def]
        return []


def call(name: str, args: str, id: str = "c1") -> AssistantTurn:
    return AssistantTurn(tool_calls=[ToolCall(id=id, name=name, arguments=args)])


@pytest.fixture
def make_runtime(tmp_path: Path):  # type: ignore[no-untyped-def]
    def _make(
        llm: FakeLLM,
        search: FakeSearch | None = None,
        max_iter: int = 4,
        registry=None,
        images=None,
        templates=None,
    ):
        ctx = ToolContext(
            llm=llm,
            search=search or FakeSearch([]),
            knowledge=FakeKnowledge(),
            presentations=MemoryPresentationStore(),
            images=images or FakeImages(),
            templates=templates or FakeTemplates(),
        )
        tracer = Tracer()
        runner = ToolRunner(registry or build_registry(), ctx, tracer, ApprovalStore())
        return Orchestrator(llm, runner, max_iter), runner, tracer, ctx

    return _make


def user(text: str) -> list[ChatMessage]:
    return [ChatMessage(role="user", content=text)]


# ---- local Postgres (pgvector) used by integration tests; they skip themselves if it is down ----
TEST_DB = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://pantalelle:pantalelle@localhost:5432/pantalelle_test"
)


class FakeEmbedder:
    """Deterministic bag-of-words hashing: similar words -> similar vectors. No network."""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            v = [0.0] * EMBEDDING_DIM
            for w in re.findall(r"\w+", t.lower()):
                v[int(hashlib.md5(w.encode()).hexdigest(), 16) % EMBEDDING_DIM] += 1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / norm for x in v])
        return out


@pytest.fixture
def test_engine():  # type: ignore[no-untyped-def]
    engine = make_engine(TEST_DB)
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except OperationalError:
        pytest.skip("test Postgres not reachable (run: docker compose up -d --wait db)")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def kb(test_engine):  # type: ignore[no-untyped-def]
    return KnowledgeService(make_session_factory(test_engine), FakeEmbedder())


@pytest.fixture
def pg_store(test_engine):  # type: ignore[no-untyped-def]
    return PgPresentationStore(make_session_factory(test_engine))
