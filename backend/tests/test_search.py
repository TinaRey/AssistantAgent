import httpx
import pytest

from app.integrations.search import SearchError, SearchResult, TavilySearchProvider
from app.schemas.tools import CompanyResearch, Finding, SearchCompanyInput
from app.tools.base import ToolError
from app.tools.search_company import search_company
from tests.conftest import FakeLLM


def provider(handler, sleeps: list[float] | None = None) -> TavilySearchProvider:  # type: ignore[no-untyped-def]
    async def fake_sleep(s: float) -> None:
        if sleeps is not None:
            sleeps.append(s)

    return TavilySearchProvider(
        "tvly-test", transport=httpx.MockTransport(handler), sleep=fake_sleep
    )


def ok_response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "results": [
                {"title": "Urgo", "url": "https://urgo.com", "content": "x" * 5000, "score": 0.9},
                {"title": "no url", "content": "skipped"},
            ]
        },
    )


async def test_tavily_request_and_parsing() -> None:
    seen: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers["authorization"]
        seen["body"] = req.read()
        return ok_response(req)

    res = await provider(handler).search("Urgo", 5)
    assert seen["auth"] == "Bearer tvly-test"
    assert b'"query":"Urgo"' in seen["body"].replace(b" ", b"")
    assert [r.url for r in res] == ["https://urgo.com"]  # result without url dropped
    assert len(res[0].snippet) == 1500  # snippet capped


async def test_429_is_retried_honoring_retry_after_then_succeeds() -> None:
    calls, sleeps = [], []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(
                429, headers={"Retry-After": "60"}, json={"detail": {"error": "x"}}
            )
        return ok_response(req)

    res = await provider(handler, sleeps).search("q")
    assert len(res) == 1 and len(calls) == 2
    assert sleeps == [5.0]  # Retry-After capped so the user is never left waiting a minute


async def test_persistent_429_and_5xx_give_up_after_bounded_retries() -> None:
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(500)

    with pytest.raises(SearchError):
        await provider(handler, []).search("q")
    assert len(calls) == 3  # 1 try + 2 retries, no more


@pytest.mark.parametrize(
    ("status", "needle"), [(401, "SEARCH_API_KEY"), (432, "quota"), (433, "dépense")]
)
async def test_non_retryable_errors_have_clear_messages(status: int, needle: str) -> None:
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(status, json={"detail": {"error": "secret provider text"}})

    with pytest.raises(SearchError, match=needle) as exc:
        await provider(handler).search("q")
    assert len(calls) == 1 and "secret provider text" not in str(exc.value)


async def test_timeout_and_garbage_responses() -> None:
    def slow(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("t", request=req)

    with pytest.raises(SearchError, match="trop de temps"):
        await provider(slow).search("q")
    with pytest.raises(SearchError, match="inattendue"):
        await provider(lambda r: httpx.Response(200, json={"oops": 1})).search("q")


class FlakySearch:
    """First query fails, the others return a result."""

    def __init__(self, fail_all: bool = False) -> None:
        self.n, self.fail_all = 0, fail_all

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        self.n += 1
        if self.fail_all or self.n == 1:
            raise SearchError("quota atteint")
        return [SearchResult(title="Urgo", url="https://urgo.com", snippet="Urgo makes things")]


async def test_company_search_partial_failure_is_reported(make_runtime) -> None:  # type: ignore[no-untyped-def]
    draft = CompanyResearch(
        company_name="Urgo", findings=[Finding(statement="ok", source_url="https://urgo.com")]
    )
    *_, ctx = make_runtime(FakeLLM(structured=[draft]), search=FlakySearch())
    out = await search_company(SearchCompanyInput(company_name="Urgo"), ctx)
    assert out.findings and any("incomplets" in w for w in out.warnings)


async def test_company_search_total_failure_becomes_tool_error(make_runtime) -> None:  # type: ignore[no-untyped-def]
    *_, ctx = make_runtime(FakeLLM(), search=FlakySearch(fail_all=True))
    with pytest.raises(ToolError, match="quota atteint"):
        await search_company(SearchCompanyInput(company_name="Urgo"), ctx)


async def test_company_search_asks_for_french_by_default(make_runtime) -> None:  # type: ignore[no-untyped-def]
    llm = FakeLLM(structured=[CompanyResearch(company_name="Urgo")])
    *_, ctx = make_runtime(llm, search=FlakySearch())
    await search_company(SearchCompanyInput(company_name="Urgo"), ctx)
    system, user = llm.structured_messages[0]
    assert "Language: fr" in user["content"] and "requested language" in system["content"]
