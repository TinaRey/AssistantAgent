from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, chat, documents, health, presentations
from app.core.config import get_settings
from app.core.internal import InternalKeyMiddleware
from app.core.security import require_auth


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.is_production and (problems := settings.production_problems()):
        raise RuntimeError("Refusing to start in production: " + "; ".join(problems))
    app = FastAPI(
        title="Pantalelle Assistant API",
        version="0.1.0",
        # No public API docs in production
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(InternalKeyMiddleware, key=settings.internal_api_key)
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    protected = [Depends(require_auth)]
    app.include_router(chat.router, prefix="/api", dependencies=protected)
    app.include_router(presentations.router, prefix="/api", dependencies=protected)
    app.include_router(documents.router, prefix="/api", dependencies=protected)
    return app


app = create_app()
