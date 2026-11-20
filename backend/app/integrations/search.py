from typing import Protocol

from pydantic import BaseModel


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class SearchProvider(Protocol):
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]: ...


class MockSearchProvider:
    """Placeholder until a provider (Tavily, Brave...) is chosen. Returns nothing: never fake data."""

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        return []
