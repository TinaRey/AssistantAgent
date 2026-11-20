from typing import Protocol

from app.schemas.tools import Passage


class KnowledgeStore(Protocol):
    async def search(self, query: str, top_k: int) -> list[Passage]: ...


class EmptyKnowledgeStore:
    """Phase 2 replaces this with Postgres-backed retrieval over uploaded documents."""

    async def search(self, query: str, top_k: int) -> list[Passage]:
        return []
