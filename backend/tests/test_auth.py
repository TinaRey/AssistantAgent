import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.security import create_session_token, limiter, verify_session_token
from app.main import app


@pytest.fixture
def client():  # type: ignore[no-untyped-def]
    app.dependency_overrides[get_settings] = lambda: Settings(
        app_password="correct horse", secret_key="s3cret", _env_file=None
    )
    limiter._failures.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_protected_routes_require_login(client) -> None:  # type: ignore[no-untyped-def]
    assert client.post("/api/chat", json={"messages": []}).status_code == 401
    assert client.get("/api/traces").status_code == 401
    assert client.get("/api/actions").status_code == 401
    assert client.get("/api/files/" + "0" * 32).status_code == 401
    assert client.get("/api/health").status_code == 200  # public


def test_login_flow(client) -> None:  # type: ignore[no-untyped-def]
    assert client.post("/api/auth/login", json={"password": "nope"}).status_code == 401
    r = client.post("/api/auth/login", json={"password": "correct horse"})
    assert r.status_code == 200
    assert "httponly" in r.headers["set-cookie"].lower()
    assert client.get("/api/auth/me").status_code == 200
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_login_is_rate_limited(client) -> None:  # type: ignore[no-untyped-def]
    for _ in range(5):
        client.post("/api/auth/login", json={"password": "bad"})
    r = client.post("/api/auth/login", json={"password": "correct horse"})
    assert r.status_code == 429


def test_login_disabled_when_unconfigured() -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    try:
        r = TestClient(app).post("/api/auth/login", json={"password": "x"})
        assert r.status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_token_tamper_and_expiry() -> None:
    tok = create_session_token("k")
    assert verify_session_token("k", tok)
    assert not verify_session_token("other", tok)
    assert not verify_session_token("k", tok[:-3] + "AAA")
    assert not verify_session_token("k", create_session_token("k", ttl_s=-1))
    assert not verify_session_token("", tok) and not verify_session_token("k", None)
