from fastapi.testclient import TestClient

from app.api.deps import build_runtime, get_runtime
from app.core.security import require_auth
from app.integrations.llm import AssistantTurn, LLMError
from app.main import app
from tests.conftest import FakeLLM


def _client(llm, tmp_path):  # type: ignore[no-untyped-def]
    rt = build_runtime(llm)
    app.dependency_overrides[get_runtime] = lambda: rt
    app.dependency_overrides[require_auth] = lambda: None
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_chat_endpoint(tmp_path) -> None:  # type: ignore[no-untyped-def]
    c = _client(FakeLLM([AssistantTurn(content="hi")]), tmp_path)
    r = c.post("/api/chat", json={"messages": [{"role": "user", "content": "yo"}]})
    assert r.status_code == 200 and r.json()["reply"] == "hi"


def test_chat_validates_input(tmp_path) -> None:  # type: ignore[no-untyped-def]
    c = _client(FakeLLM(), tmp_path)
    assert c.post("/api/chat", json={"messages": []}).status_code == 422


def test_llm_errors_map_to_http_status(tmp_path) -> None:  # type: ignore[no-untyped-def]
    class Limited(FakeLLM):
        async def chat(self, messages, tools):  # type: ignore[no-untyped-def]
            raise LLMError("rate_limit", "slow down")

    c = _client(Limited(), tmp_path)
    r = c.post("/api/chat", json={"messages": [{"role": "user", "content": "yo"}]})
    assert r.status_code == 429 and r.json()["detail"] == "slow down"
