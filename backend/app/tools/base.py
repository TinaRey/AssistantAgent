from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from app.integrations.images import ImageProvider
from app.integrations.knowledge import KnowledgeStore
from app.integrations.llm import LLMClient
from app.integrations.search import SearchProvider
from app.integrations.templates import TemplateSource
from app.services.presentations import PresentationStore


class ToolError(Exception):
    """Expected, user-presentable failure. The message is sent back to the model."""


@dataclass(frozen=True)
class ToolContext:
    llm: LLMClient
    search: SearchProvider
    knowledge: KnowledgeStore
    presentations: PresentationStore
    images: ImageProvider
    templates: TemplateSource


ToolFunc = Callable[[Any, ToolContext], Awaitable[BaseModel]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    func: ToolFunc
    timeout_s: float = 45.0
    # True for anything with an external side effect (sending, publishing...).
    # Such tools are NEVER run by the model loop: they wait for human approval.
    requires_approval: bool = False
    # True when the UI shows the result as a card: the model is told not to repeat it in the chat.
    ui_card: bool = False

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }
