"""Image generation (OpenAI). Only called on explicit user request: every image costs money."""

import base64
import logging
from typing import Protocol

from app.integrations.llm import LLMError

logger = logging.getLogger(__name__)

PROMPT_MAX_CHARS = 700


class ImageProvider(Protocol):
    async def generate(self, prompt: str) -> bytes: ...


def build_image_prompt(subject: str, style: str | None) -> str:
    """Safe, brand-neutral prompt: illustration only, no text (models render text poorly) or logos."""
    parts = [
        "Illustration for a business presentation slide.",
        f"Subject: {subject.strip()}.",
        f"Visual universe and colors: {style.strip()}." if style and style.strip() else "",
        "Clean composition, soft natural light, square format. "
        "No text, no letters, no logos, no watermark.",
    ]
    return " ".join(p for p in parts if p)[:PROMPT_MAX_CHARS]


class OpenAIImageProvider:
    def __init__(self, api_key: str, model: str, quality: str, size: str, timeout_s: float) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_s, max_retries=1)
        self._model, self._quality, self._size = model, quality, size

    async def generate(self, prompt: str) -> bytes:
        import openai

        try:
            resp = await self._client.images.generate(
                model=self._model,
                prompt=prompt,
                size=self._size,  # type: ignore[arg-type]
                quality=self._quality,  # type: ignore[arg-type]
                n=1,
            )
        except openai.RateLimitError as exc:
            raise LLMError(
                "rate_limit", "Le service d'images est limité. Réessayez dans un instant."
            ) from exc
        except openai.APITimeoutError as exc:
            raise LLMError("timeout", "La génération d'image a pris trop de temps.") from exc
        except openai.AuthenticationError as exc:
            raise LLMError("auth", "Le service d'images a refusé la clé API.") from exc
        except openai.BadRequestError as exc:
            # e.g. unknown model name or a prompt refused by the safety system
            logger.warning("Image request rejected: %s", type(exc).__name__)
            raise LLMError(
                "bad_output", "La demande d'image a été refusée (modèle ou contenu)."
            ) from exc
        except openai.APIError as exc:
            logger.warning("Image generation failed: %s", type(exc).__name__)
            raise LLMError("unavailable", "Le service d'images est indisponible.") from exc
        b64 = resp.data[0].b64_json if resp.data else None
        if not b64:
            raise LLMError("bad_output", "Le service d'images n'a renvoyé aucune image.")
        return base64.b64decode(b64)


class UnconfiguredImageProvider:
    async def generate(self, prompt: str) -> bytes:
        raise LLMError(
            "auth", "OPENAI_API_KEY n'est pas configurée : génération d'image impossible."
        )
