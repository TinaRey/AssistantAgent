"""Single-user password auth with a stateless signed session cookie (stdlib only)."""

import base64
import hashlib
import hmac
import time
from collections import defaultdict

from fastapi import Cookie, Depends, HTTPException

from app.core.config import Settings, get_settings

COOKIE_NAME = "session"
SESSION_TTL_S = 7 * 24 * 3600


def _sign(secret: str, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_session_token(secret: str, ttl_s: int = SESSION_TTL_S) -> str:
    payload = str(int(time.time()) + ttl_s)
    sig = _sign(secret, payload)
    return base64.urlsafe_b64encode(f"{payload}.{sig}".encode()).decode()


def verify_session_token(secret: str, token: str | None) -> bool:
    if not token or not secret:
        return False
    try:
        payload, sig = base64.urlsafe_b64decode(token.encode()).decode().split(".", 1)
        return hmac.compare_digest(sig, _sign(secret, payload)) and int(payload) > time.time()
    except ValueError:
        return False


def check_password(settings: Settings, candidate: str) -> bool:
    if not settings.app_password:
        return False
    return hmac.compare_digest(candidate.encode(), settings.app_password.encode())


def require_auth(
    session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    settings: Settings = Depends(get_settings),
) -> None:
    if not verify_session_token(settings.secret_key, session):
        raise HTTPException(401, "Authentication required")


class LoginLimiter:
    """Naive in-memory brake on password guessing (per client IP)."""

    def __init__(self, max_failures: int = 5, window_s: int = 300) -> None:
        self.max_failures, self.window_s = max_failures, window_s
        self._failures: dict[str, list[float]] = defaultdict(list)

    def _recent(self, key: str) -> list[float]:
        cutoff = time.time() - self.window_s
        self._failures[key] = [t for t in self._failures[key] if t > cutoff]
        return self._failures[key]

    def blocked(self, key: str) -> bool:
        return len(self._recent(key)) >= self.max_failures

    def fail(self, key: str) -> None:
        self._recent(key).append(time.time())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


limiter = LoginLimiter()
global_limiter = LoginLimiter(max_failures=30, window_s=300)
