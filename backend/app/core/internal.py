"""Shared-secret gate: in production only the Next.js proxy may call the API.

The backend is a public web service on Render's free plan, so without this anyone could try passwords on
/api/auth/login directly. When INTERNAL_API_KEY is set, every /api request except the health check must
carry it in `X-Internal-Key`; the proxy also forwards the real client IP in `X-Client-IP` (trusted only
because the key matched).
"""

import hmac
import json

from starlette.types import ASGIApp, Receive, Scope, Send

OPEN_PATHS = {"/api/health"}


class InternalKeyMiddleware:
    def __init__(self, app: ASGIApp, key: str) -> None:
        self.app, self.key = app, key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.key or scope["path"] in OPEN_PATHS:
            await self.app(scope, receive, send)
            return
        headers = {k.lower(): v for k, v in scope["headers"]}
        provided = headers.get(b"x-internal-key", b"").decode("latin-1")
        if not hmac.compare_digest(provided.encode(), self.key.encode()):
            body = json.dumps({"detail": "Forbidden"}).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"content-length", str(len(body)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return
        client_ip = headers.get(b"x-client-ip", b"").decode("latin-1").strip()[:64]
        if client_ip:
            scope.setdefault("state", {})["client_ip"] = client_ip
        await self.app(scope, receive, send)
