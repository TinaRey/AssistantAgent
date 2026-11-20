from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, chat, documents, files, health
from app.core.config import get_settings
from app.core.security import require_auth


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Pantalelle Assistant API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    protected = [Depends(require_auth)]
    app.include_router(chat.router, prefix="/api", dependencies=protected)
    app.include_router(files.router, prefix="/api", dependencies=protected)
    app.include_router(documents.router, prefix="/api", dependencies=protected)
    return app


app = create_app()
