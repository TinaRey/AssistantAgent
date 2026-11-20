from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.db.base import make_engine, make_session_factory
from app.integrations.embeddings import Embedder, OpenAIEmbedder, UnconfiguredEmbedder
from app.integrations.knowledge import EmptyKnowledgeStore, KnowledgeStore
from app.integrations.llm import LLMClient, OpenAIClient, UnconfiguredLLM
from app.integrations.search import MockSearchProvider
from app.knowledge_base.service import KnowledgeService
from app.services.orchestrator import Orchestrator
from app.services.tool_runner import ApprovalStore, ToolRunner
from app.services.tracing import Tracer
from app.tools.base import ToolContext
from app.tools.registry import build_registry


@dataclass
class Runtime:
    orchestrator: Orchestrator
    runner: ToolRunner
    tracer: Tracer
    storage_dir: Path
    knowledge: KnowledgeService | None = None


def build_runtime(
    llm: LLMClient | None = None,
    storage_dir: Path | None = None,
    knowledge: KnowledgeService | None = None,
) -> Runtime:
    s = get_settings()
    if llm is None:
        llm = (
            OpenAIClient(s.openai_api_key, s.openai_model, s.llm_timeout_s)
            if s.openai_api_key
            else UnconfiguredLLM()
        )
    if knowledge is None and s.database_url:
        embedder: Embedder = (
            OpenAIEmbedder(s.openai_api_key, s.embedding_model, s.llm_timeout_s)
            if s.openai_api_key
            else UnconfiguredEmbedder()
        )
        knowledge = KnowledgeService(make_session_factory(make_engine(s.database_url)), embedder)
    store: KnowledgeStore = knowledge or EmptyKnowledgeStore()
    storage = storage_dir or Path(s.storage_dir)
    ctx = ToolContext(llm=llm, search=MockSearchProvider(), knowledge=store, storage_dir=storage)
    tracer = Tracer()
    runner = ToolRunner(build_registry(), ctx, tracer, ApprovalStore())
    orchestrator = Orchestrator(llm, runner, s.max_tool_iterations)
    return Runtime(orchestrator, runner, tracer, storage, knowledge)


@lru_cache
def get_runtime() -> Runtime:
    return build_runtime()
