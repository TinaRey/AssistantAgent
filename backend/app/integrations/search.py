import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

SNIPPET_MAX_CHARS = 1500  # bounds the tokens a single result can cost downstream


class SearchError(Exception):
    """Search failed. The message is user-presentable and never contains the query."""


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class SearchProvider(Protocol):
    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]: ...


class MockSearchProvider:
    """Used when SEARCH_API_KEY is unset. Returns nothing: never fake data."""

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        return []


class TavilySearchProvider:
    URL = "https://api.tavily.com/search"
    MAX_RETRIES = 2
    MAX_WAIT_S = 5.0

    def __init__(
        self,
        api_key: str,
        timeout_s: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._client = httpx.AsyncClient(
            timeout=timeout_s,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        self._sleep = sleep

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        body = {
            "query": query,
            "search_depth": "basic",
            "max_results": max(1, min(max_results, 10)),
            "include_answer": False,
        }
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                resp = await self._client.post(self.URL, json=body)
            except httpx.TimeoutException as exc:
                raise SearchError("Le moteur de recherche a mis trop de temps à répondre.") from exc
            except httpx.HTTPError as exc:
                logger.warning("Search transport error: %s", type(exc).__name__)
                raise SearchError("Le moteur de recherche est injoignable.") from exc

            if resp.status_code == 200:
                return self._parse(resp)
            if resp.status_code == 429 and attempt < self.MAX_RETRIES:
                await self._sleep(self._retry_after(resp))
                continue
            if resp.status_code >= 500 and attempt < self.MAX_RETRIES:
                await self._sleep(1.0 + attempt)
                continue
            raise SearchError(self._explain(resp.status_code))
        raise SearchError("Le moteur de recherche est indisponible.")  # pragma: no cover

    @classmethod
    def _retry_after(cls, resp: httpx.Response) -> float:
        try:
            return min(float(resp.headers.get("Retry-After", "2")), cls.MAX_WAIT_S)
        except ValueError:
            return 2.0

    @staticmethod
    def _explain(status: int) -> str:
        logger.warning("Search provider returned HTTP %d", status)
        return {
            401: "La clé du moteur de recherche (SEARCH_API_KEY) est invalide.",
            429: "Trop de recherches en peu de temps. Réessayez dans un instant.",
            432: "Le quota du moteur de recherche est atteint.",
            433: "La limite de dépense du moteur de recherche est atteinte.",
        }.get(status, "Le moteur de recherche est indisponible.")

    @staticmethod
    def _parse(resp: httpx.Response) -> list[SearchResult]:
        try:
            items = resp.json()["results"]
            return [
                SearchResult(
                    title=str(i.get("title", "")),
                    url=str(i["url"]),
                    snippet=str(i.get("content", ""))[:SNIPPET_MAX_CHARS],
                )
                for i in items
                if i.get("url")
            ]
        except (ValueError, KeyError, TypeError) as exc:
            raise SearchError("Réponse inattendue du moteur de recherche.") from exc
