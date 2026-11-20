import logging
from typing import Protocol

from app.integrations.llm import LLMError

logger = logging.getLogger(__name__)
BATCH = 64


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    def __init__(self, api_key: str, model: str, timeout_s: float) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_s, max_retries=2)
        self._model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import openai

        out: list[list[float]] = []
        try:
            for i in range(0, len(texts), BATCH):
                resp = await self._client.embeddings.create(
                    model=self._model, input=texts[i : i + BATCH]
                )
                out += [d.embedding for d in resp.data]
        except openai.RateLimitError as exc:
            raise LLMError("rate_limit", "The AI service is rate-limited. Retry shortly.") from exc
        except openai.APITimeoutError as exc:
            raise LLMError("timeout", "The AI service took too long to answer.") from exc
        except openai.AuthenticationError as exc:
            raise LLMError("auth", "The AI service rejected the API key.") from exc
        except Exception as exc:
            logger.warning("Embedding call failed: %s", type(exc).__name__)
            raise LLMError("unavailable", "The AI service is currently unavailable.") from exc
        return out


class UnconfiguredEmbedder:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise LLMError("auth", "OPENAI_API_KEY is not configured.")
