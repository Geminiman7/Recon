import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, Request, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.error_handling import http_exception_handler, validation_exception_handler, unhandled_exception_handler
import uuid
from app.models.job import ReconciliationJob
from app.models.processor import Processor
from app.models.upload import Upload
from app.models.column_mapping import ColumnMapping
from app.models.reconciliation_result import ReconciliationResult
from app.models.password_reset_token import PasswordResetToken
from app.models.audit_log import AuditLog
from app.models.notification import Notification
from app.models.subscription import Plan, Subscription, BillingPayment, BillingEvent
from app.api.auth import router as auth_router
from app.api.dashboard import router as dashboard_router
from app.api.jobs import router as jobs_router
from app.api.users import router as users_router
from app.api.uploads import router as uploads_router
from app.api.processors import router as processors_router
from app.api.mapping import router as mapping_router
from app.api.notifications import router as notifications_router
from app.api.billing import router as billing_router
from app.api.settings import router as settings_router
# Import all models
from app.models.company import Company
from app.models.user import User,UserRole
from app.core.config import settings
from app.core.database import get_db
from app.core.celery_app import celery_app
import sentry_sdk
import logging
try:
    from importlib import import_module

    jsonlogger = import_module("pythonjsonlogger.json")
except ImportError:
    jsonlogger = None

handler = logging.StreamHandler()
formatter = (
    jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s")
    if jsonlogger
    else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
)
handler.setFormatter(formatter)
logger = logging.getLogger("recon")
logger.handlers = [handler]
logger.setLevel(settings.LOG_LEVEL)
logger.propagate = False



app = FastAPI(
    title="Recon API",
    version="1.0.0"
)


@app.on_event("startup")
async def startup_event():
    if settings.SENTRY_DSN:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                environment=settings.ENVIRONMENT,
                traces_sample_rate=0.1 if settings.is_production else 1.0,
                profiles_sample_rate=0.1 if settings.is_production else 1.0,
                release="recon@1.0.0",
            )
            logger.info("Sentry initialized.")
        except Exception as exc:
            logger.warning("Failed to initialize Sentry: %s", exc)


from app.core.sessions import validate_csrf
from app.core.throttling import throttle
from fastapi import HTTPException

@app.middleware("http")
async def request_security(request: Request, call_next):
    try:
        if request.url.path.startswith("/auth") and request.url.path != "/auth/csrf":
            throttle("ip", request.client.host if request.client else "unknown", settings.AUTH_RATE_LIMIT)
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.url.path != "/billing/webhooks/paystack":
            validate_csrf(request)
    except HTTPException as exc:
        return await http_exception_handler(request, exc)
    response = await call_next(request)
    if request.url.path not in {"/health/live", "/health/ready"}:
        response.headers["Cache-Control"] = "no-store"
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(
        "HTTP %s %s",
        request.method,
        request.url.path,
        extra={"request_id": getattr(request.state, "request_id", None)},
    )
    response = await call_next(request)
    logger.info(
        "HTTP %s %s -> %s",
        request.method,
        request.url.path,
        response.status_code,
        extra={"request_id": getattr(request.state, "request_id", None)},
    )
    return response


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = f"req_{uuid.uuid4().hex}"
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    return response


app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(dashboard_router)
app.include_router(users_router)
app.include_router(uploads_router)
app.include_router(processors_router)
app.include_router(mapping_router)
app.include_router(notifications_router)
app.include_router(billing_router)
app.include_router(settings_router)

@app.get("/")
def home():
    return {
        "message": "Recon API is running."
    }


@app.get("/health/live")
def health_live():
    return {"status": "alive", "service": "Recon API"}


@app.get("/health/ready")
def health_ready(db=Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    redis_ok = False
    if settings.REDIS_URL:
        try:
            import redis
            r = redis.from_url(settings.REDIS_URL, socket_timeout=2, socket_connect_timeout=2)
            r.ping()
            redis_ok = True
        except Exception:
            redis_ok = False

    celery_ok = False
    if redis_ok:
        try:
            insp = celery_app.control.inspect(timeout=2)
            celery_ok = bool(insp.ping())
        except Exception:
            celery_ok = False

    ready = db_ok and redis_ok and celery_ok
    payload = {
        "status": "ready" if ready else "unavailable",
        "service": "Recon API",
        "checks": {
            "database": "ok" if db_ok else "failed",
            "redis": "ok" if redis_ok else "failed",
            "celery": "ok" if celery_ok else "failed",
        },
    }
    return JSONResponse(content=payload, status_code=200 if ready else 503)


from app.api.reconciliation import router as reconciliation_router
app.include_router(reconciliation_router)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-Id", "X-CSRF-Token"],
)
