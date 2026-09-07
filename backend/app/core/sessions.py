"""Host-only cookies and signed, session-bound double-submit CSRF tokens."""
import hashlib
import hmac
import secrets
import time
from fastapi import HTTPException, Request, Response
from app.core.config import settings

SESSION_COOKIE = "__Host-recon_session" if settings.is_production else "recon_session"
CSRF_COOKIE = "__Host-recon_csrf" if settings.is_production else "recon_csrf"


def signature(value, session):
    binding = hashlib.sha256(session.encode()).hexdigest()
    return hmac.new(settings.SECRET_KEY.encode(), f"{value}:{binding}".encode(), hashlib.sha256).hexdigest()


def issue_csrf(response: Response, session: str = ""):
    value = f"{int(time.time())}.{secrets.token_hex(24)}"
    token = f"{value}.{signature(value, session)}"
    response.set_cookie(CSRF_COOKIE, token, secure=settings.is_production, httponly=False,
                        samesite="lax", path="/", max_age=3600)
    response.headers["Cache-Control"] = "no-store"
    return token


def validate_csrf(request: Request):
    token = request.headers.get("X-CSRF-Token", "")
    cookie = request.cookies.get(CSRF_COOKIE, "")
    try:
        stamp, nonce, mac = token.split(".")
        age = time.time() - int(stamp)
        valid = (0 <= age <= 3600 and len(nonce) == 48 and
                 hmac.compare_digest(token, cookie) and
                 hmac.compare_digest(mac, signature(f"{stamp}.{nonce}", request.cookies.get(SESSION_COOKIE, ""))))
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise HTTPException(403, "Your security token expired. Refresh the page and try again.")
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in {settings.FRONTEND_URL.rstrip("/"), *settings.cors_origins_list}:
        raise HTTPException(403, "Request origin is not allowed.")


def set_session(response: Response, token: str):
    response.set_cookie(SESSION_COOKIE, token, secure=settings.is_production, httponly=True,
                        samesite="lax", path="/", max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    issue_csrf(response, token)


def clear_session(response: Response):
    response.delete_cookie(SESSION_COOKIE, path="/", secure=settings.is_production, httponly=True, samesite="lax")
    issue_csrf(response)
