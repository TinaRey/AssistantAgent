from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.security import (
    COOKIE_NAME,
    SESSION_TTL_S,
    check_password,
    create_session_token,
    global_limiter,
    limiter,
    require_auth,
)

router = APIRouter(prefix="/auth")


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=500)


@router.post("/login")
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> dict[str, bool]:
    if not settings.app_password or not settings.secret_key:
        raise HTTPException(503, "Authentication is not configured (APP_PASSWORD / SECRET_KEY).")
    # Behind the proxy the real IP comes from X-Client-IP (set by InternalKeyMiddleware).
    ip = getattr(request.state, "client_ip", None) or (
        request.client.host if request.client else "unknown"
    )
    if limiter.blocked(ip) or global_limiter.blocked("*"):
        raise HTTPException(429, "Too many attempts. Try again in a few minutes.")
    if not check_password(settings, body.password):
        limiter.fail(ip)
        global_limiter.fail("*")  # backstop if the IP header is spoofed or shared
        raise HTTPException(401, "Wrong password")
    limiter.reset(ip)
    response.set_cookie(
        COOKIE_NAME,
        create_session_token(settings.secret_key),
        max_age=SESSION_TTL_S,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@router.get("/me", dependencies=[Depends(require_auth)])
def me() -> dict[str, bool]:
    return {"authenticated": True}
