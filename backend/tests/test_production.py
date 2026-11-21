import pytest
from fastapi.testclient import TestClient

from app import main
from app.core.config import Settings, get_settings
from app.core.security import global_limiter, limiter

GOOD = {
    "environment": "production",
    "app_password": "a-long-password",
    "secret_key": "s" * 40,
    "internal_api_key": "k" * 40,
    "cookie_secure": True,
    "database_url": "postgresql://u:p@db.example.com:5432/postgres",
}


def settings(**kw) -> Settings:  # type: ignore[no-untyped-def]
    return Settings(**{**GOOD, **kw}, _env_file=None)


def make_app(monkeypatch, s: Settings):  # type: ignore[no-untyped-def]
    monkeypatch.setattr(main, "get_settings", lambda: s)
    app = main.create_app()
    app.dependency_overrides[get_settings] = lambda: s
    return app


@pytest.fixture(autouse=True)
def _clean_limiters():  # type: ignore[no-untyped-def]
    limiter._failures.clear()
    global_limiter._failures.clear()
    yield
    limiter._failures.clear()
    global_limiter._failures.clear()


# ---- configuration -------------------------------------------------------------------------
def test_database_url_accepts_the_plain_urls_hosts_give() -> None:
    assert (
        Settings(database_url="postgres://u:p@h/db", _env_file=None).database_url
        == "postgresql+psycopg://u:p@h/db"
    )
    assert Settings(database_url="postgresql://u:p@h/db", _env_file=None).database_url.startswith(
        "postgresql+psycopg://"
    )
    assert (
        Settings(database_url="postgresql+psycopg://u:p@h/db", _env_file=None).database_url
        == "postgresql+psycopg://u:p@h/db"
    )
    assert Settings(database_url="", _env_file=None).database_url == ""


def test_production_problems_are_listed() -> None:
    assert settings().production_problems() == []
    assert len(Settings(environment="production", _env_file=None).production_problems()) == 5
    assert "APP_PASSWORD" in settings(app_password="short").production_problems()[0]
    assert any("COOKIE_SECURE" in p for p in settings(cookie_secure=False).production_problems())
    assert any(
        "INTERNAL_API_KEY" in p for p in settings(internal_api_key="x").production_problems()
    )


def test_production_refuses_to_start_with_weak_settings(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(main, "get_settings", lambda: settings(secret_key="", cookie_secure=False))
    with pytest.raises(RuntimeError, match="SECRET_KEY.*COOKIE_SECURE"):
        main.create_app()


def test_development_does_not_enforce_production_rules(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    app = make_app(monkeypatch, Settings(_env_file=None))
    assert TestClient(app).get("/docs").status_code == 200  # docs stay available locally


def test_production_hides_api_docs(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client = TestClient(make_app(monkeypatch, settings()))
    h = {"X-Internal-Key": GOOD["internal_api_key"]}
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path, headers=h).status_code == 404


# ---- internal key --------------------------------------------------------------------------
def test_internal_key_protects_everything_but_the_health_check(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client = TestClient(make_app(monkeypatch, settings()))
    assert client.get("/api/health").status_code == 200  # Render's health check has no key
    for path in ("/api/auth/me", "/api/documents", "/api/traces"):
        assert client.get(path).status_code == 403
    assert client.post("/api/auth/login", json={"password": "a-long-password"}).status_code == 403
    assert client.get("/api/auth/me", headers={"X-Internal-Key": "wrong"}).status_code == 403
    assert client.get("/api/auth/me", headers={"X-Internal-Key": ""}).status_code == 403
    ok = {"X-Internal-Key": GOOD["internal_api_key"]}
    assert client.get("/api/auth/me", headers=ok).status_code == 401  # through: now needs a session


def test_full_login_through_the_proxy_headers(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # https: a Secure cookie is never sent back over plain http
    client = TestClient(make_app(monkeypatch, settings()), base_url="https://testserver")
    h = {"X-Internal-Key": GOOD["internal_api_key"]}
    r = client.post("/api/auth/login", json={"password": "a-long-password"}, headers=h)
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "secure" in cookie and "httponly" in cookie and "samesite=lax" in cookie
    assert client.get("/api/auth/me", headers=h).status_code == 200


def test_rate_limit_uses_the_forwarded_client_ip(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client = TestClient(make_app(monkeypatch, settings()))
    key = {"X-Internal-Key": GOOD["internal_api_key"]}
    attacker = {**key, "X-Client-IP": "203.0.113.7"}
    for _ in range(5):
        assert (
            client.post("/api/auth/login", json={"password": "nope"}, headers=attacker).status_code
            == 401
        )
    assert (
        client.post(
            "/api/auth/login", json={"password": "a-long-password"}, headers=attacker
        ).status_code
        == 429
    )
    # another real user is not locked out by the attacker (all requests share the proxy's own address)
    other = {**key, "X-Client-IP": "198.51.100.2"}
    assert (
        client.post(
            "/api/auth/login", json={"password": "a-long-password"}, headers=other
        ).status_code
        == 200
    )


def test_client_ip_header_is_ignored_without_the_key(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client = TestClient(make_app(monkeypatch, settings()))
    r = client.post("/api/auth/login", json={"password": "x"}, headers={"X-Client-IP": "1.2.3.4"})
    assert r.status_code == 403 and "1.2.3.4" not in limiter._failures


def test_global_backstop_stops_spoofed_ip_guessing(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client = TestClient(make_app(monkeypatch, settings()))
    key = {"X-Internal-Key": GOOD["internal_api_key"]}
    for i in range(30):  # a different IP each time defeats the per-IP limit
        r = client.post(
            "/api/auth/login",
            json={"password": "nope"},
            headers={**key, "X-Client-IP": f"10.0.0.{i}"},
        )
        assert r.status_code == 401
    brand_new = {**key, "X-Client-IP": "10.9.9.9"}
    assert (
        client.post(
            "/api/auth/login", json={"password": "a-long-password"}, headers=brand_new
        ).status_code
        == 429
    )


def test_without_an_internal_key_nothing_changes_in_development(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    client = TestClient(
        make_app(monkeypatch, Settings(app_password="pw", secret_key="s", _env_file=None))
    )
    assert client.post("/api/auth/login", json={"password": "pw"}).status_code == 200
