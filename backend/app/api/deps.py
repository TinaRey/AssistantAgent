from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.integrations.knowledge import EmptyKnowledgeStore
from app.integrations.llm import LLMClient, OpenAIClient, UnconfiguredLLM
from app.integrations.search import MockSearchProvider
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


def build_runtime(llm: LLMClient | None = None, storage_dir: Path | None = None) -> Runtime:
    s = get_settings()
    if llm is None:
        llm = (
            OpenAIClient(s.openai_api_key, s.openai_model, s.llm_timeout_s)
            if s.openai_api_key
            else UnconfiguredLLM()
        )
    storage = storage_dir or Path(s.storage_dir)
    ctx = ToolContext(
        llm=llm, search=MockSearchProvider(), knowledge=EmptyKnowledgeStore(), storage_dir=storage
    )
    tracer = Tracer()
    runner = ToolRunner(build_registry(), ctx, tracer, ApprovalStore())
    return Runtime(Orchestrator(llm, runner, s.max_tool_iterations), runner, tracer, storage)


@lru_cache
def get_runtime() -> Runtime:
    return build_runtime()
