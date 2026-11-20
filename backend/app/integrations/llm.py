"""LLM integration. Everything else depends on the `LLMClient` protocol only."""

import logging
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind  # "rate_limit" | "timeout" | "auth" | "unavailable" | "bad_output"


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: str  # raw JSON string, validated later by the tool runner


class AssistantTurn(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = []


class LLMClient(Protocol):
    async def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AssistantTurn: ...

    async def structured(self, messages: list[dict[str, Any]], schema: type[T]) -> T: ...


class OpenAIClient:
    def __init__(self, api_key: str, model: str, timeout_s: float) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_s, max_retries=2)
        self._model = model

    async def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AssistantTurn:
        try:
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=tools or None,  # type: ignore[arg-type]
            )
        except Exception as exc:
            raise _map_error(exc) from exc
        msg = resp.choices[0].message
        calls = [
            ToolCall(id=c.id, name=c.function.name, arguments=c.function.arguments)
            for c in (msg.tool_calls or [])
            if c.type == "function"
        ]
        return AssistantTurn(content=msg.content, tool_calls=calls)

    async def structured(self, messages: list[dict[str, Any]], schema: type[T]) -> T:
        try:
            resp = await self._client.beta.chat.completions.parse(
                model=self._model,
                messages=messages,
                response_format=schema,  # type: ignore[arg-type]
            )
        except Exception as exc:
            raise _map_error(exc) from exc
        parsed = resp.choices[0].message.parsed
        if parsed is None:
            raise LLMError("bad_output", "The model did not return valid structured output.")
        return parsed


def _map_error(exc: Exception) -> LLMError:
    import openai

    # Log the exception type only: messages may echo prompt content.
    logger.warning("LLM call failed: %s", type(exc).__name__)
    if isinstance(exc, openai.RateLimitError):
        return LLMError("rate_limit", "The AI service is rate-limited. Please retry shortly.")
    if isinstance(exc, openai.APITimeoutError):
        return LLMError("timeout", "The AI service took too long to answer.")
    if isinstance(exc, openai.AuthenticationError):
        return LLMError("auth", "The AI service rejected the API key.")
    return LLMError("unavailable", "The AI service is currently unavailable.")


class UnconfiguredLLM:
    """Used when no API key is set, so the app boots and fails with a clear message."""

    async def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AssistantTurn:
        raise LLMError("auth", "OPENAI_API_KEY is not configured.")

    async def structured(self, messages: list[dict[str, Any]], schema: type[T]) -> T:
        raise LLMError("auth", "OPENAI_API_KEY is not configured.")
