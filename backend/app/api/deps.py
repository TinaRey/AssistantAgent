from dataclasses import dataclass
from functools import lru_cache

from app.core.config import get_settings
from app.db.base import make_engine, make_session_factory
from app.integrations.embeddings import Embedder, OpenAIEmbedder, UnconfiguredEmbedder
from app.integrations.images import ImageProvider, OpenAIImageProvider, UnconfiguredImageProvider
from app.integrations.knowledge import EmptyKnowledgeStore, KnowledgeStore
from app.integrations.llm import LLMClient, OpenAIClient, UnconfiguredLLM
from app.integrations.search import MockSearchProvider, SearchProvider, TavilySearchProvider
from app.integrations.templates import EmptyTemplateSource, TemplateSource
from app.knowledge_base.service import KnowledgeService
from app.services.orchestrator import Orchestrator
from app.services.presentations import (
    MemoryPresentationStore,
    PgPresentationStore,
    PresentationStore,
)
from app.services.tool_runner import ApprovalStore, ToolRunner
from app.services.tracing import Tracer
from app.tools.base import ToolContext
from app.tools.registry import build_registry


@dataclass
class Runtime:
    orchestrator: Orchestrator
    runner: ToolRunner
    tracer: Tracer
    presentations: PresentationStore
    images: ImageProvider
    knowledge: KnowledgeService | None = None


def build_runtime(
    llm: LLMClient | None = None,
    knowledge: KnowledgeService | None = None,
    presentations: PresentationStore | None = None,
    images: ImageProvider | None = None,
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
    search: SearchProvider = (
        TavilySearchProvider(s.search_api_key, s.search_timeout_s)
        if s.search_api_key
        else MockSearchProvider()
    )
    if presentations is None:
        presentations = (
            PgPresentationStore(make_session_factory(make_engine(s.database_url)))
            if s.database_url
            else MemoryPresentationStore()
        )
    if images is None:
        images = (
            OpenAIImageProvider(
                s.openai_api_key, s.image_model, s.image_quality, s.image_size, s.image_timeout_s
            )
            if s.openai_api_key
            else UnconfiguredImageProvider()
        )
    templates: TemplateSource = knowledge or EmptyTemplateSource()
    ctx = ToolContext(
        llm=llm,
        search=search,
        knowledge=store,
        presentations=presentations,
        images=images,
        templates=templates,
    )
    tracer = Tracer()
    runner = ToolRunner(build_registry(), ctx, tracer, ApprovalStore())
    orchestrator = Orchestrator(llm, runner, s.max_tool_iterations)
    return Runtime(orchestrator, runner, tracer, presentations, images, knowledge)


@lru_cache
def get_runtime() -> Runtime:
    return build_runtime()
