import logging
import uuid

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings

logger = logging.getLogger("recon")


def problem(status: int, detail=None, request_id: str | None = None):
    definitions = {
        400: ("validation", "VALIDATION_FAILED", "Please review the information provided.", "Check the highlighted details and try again."),
        401: ("authentication", "AUTHENTICATION_REQUIRED", "Sign in is required.", "Sign in again, then repeat this action."),
        402: ("billing", "SUBSCRIPTION_REQUIRED", "Your subscription needs attention.", "Open Subscription to restore access."),
        403: ("authorization", "PERMISSION_DENIED", "You do not have access to do that.", "Ask a workspace administrator to update your access."),
        404: ("validation", "RESOURCE_NOT_FOUND", "We could not find that item.", "Refresh the page and confirm the item still exists."),
        409: ("validation", "CONFLICT", "This action conflicts with existing information.", "Refresh the page and try again."),
        422: ("validation", "VALIDATION_FAILED", "Some information needs attention.", "Correct the highlighted fields and try again."),
        429: ("network", "RATE_LIMITED", "Too many requests were sent.", "Wait a moment, then try again."),
    }
    category, code, title, action = definitions.get(status, ("system", "SYSTEM_ERROR", "We could not complete that action.", "Try again shortly. If this continues, contact support."))
    message = detail if isinstance(detail, str) and status < 500 else title
    return {"type": f"https://docs.recon.com/errors/{code.lower()}", "title": title, "status": status,
            "detail": message, "code": code, "category": category, "action": action, "request_id": request_id}


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(problem(exc.status_code, exc.detail, getattr(request.state, "request_id", None)), status_code=exc.status_code, media_type="application/problem+json", headers=exc.headers)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = problem(422, request_id=getattr(request.state, "request_id", None))
    body["errors"] = [{"field": ".".join(str(part) for part in error["loc"] if part != "body"), "message": error["msg"]} for error in exc.errors()]
    return JSONResponse(body, status_code=422, media_type="application/problem+json")


async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.exception("Unhandled exception on %s %s (request_id=%s)", request.method, request.url.path, request_id, exc_info=exc)
    if settings.SENTRY_DSN:
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(exc)
        except Exception:
            pass
    return JSONResponse(problem(500, request_id=request_id), status_code=500, media_type="application/problem+json", headers={"X-Request-Id": request_id or "unknown", "Cache-Control": "no-store"})
