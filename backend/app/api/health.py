from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ok",
        # Booleans only: never expose secret values.
        "llm_configured": bool(settings.openai_api_key),
        "model": settings.openai_model,
    }
