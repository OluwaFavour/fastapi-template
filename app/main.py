from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request, status
from sqlalchemy import text
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

# Register ALL ORM models before any CRUD/dependency import can trigger
# SQLAlchemy mapper configuration (selectinload, relationship resolution, etc.)
import app.core.db.models  # noqa: F401
import app.apps.example_app.db.models  # noqa: F401

from app.core.dependencies import get_async_session
from app.core.config import settings, app_logger
from app.core.exceptions.handlers import (
    authentication_exception_handler,
    bad_request_exception_handler,
    conflict_exception_handler,
    database_exception_handler,
    exception_schema,
    forbidden_exception_handler,
    general_exception_handler,
    not_found_exception_handler,
    not_implemented_exception_handler,
    oauth_exception_handler,
    otp_expired_exception_handler,
    otp_invalid_exception_handler,
    payment_required_exception_handler,
    rate_limit_exception_handler,
    too_many_attempts_exception_handler,
    value_error_exception_handler,
)
from app.core.exceptions.types import (
    AppException,
    AuthenticationException,
    BadRequestException,
    ConflictException,
    DatabaseException,
    ForbiddenException,
    NotFoundException,
    NotImplementedException,
    OAuthException,
    OTPExpiredException,
    OTPInvalidException,
    PaymentRequiredException,
    RateLimitExceededException,
    TooManyAttemptsException,
)
from app.core.logger import init_sentry
from app.apps.example_app.routers import item_router
from app.admin import init_admin
from app.infrastructure.scheduler import scheduler, initialize_scheduler
from app.infrastructure.messaging import start_consumers, publish_event
from app.infrastructure.messaging.connection import get_connection
from app.core.services.event_publisher import register_publisher
from app.core.services.lifecycle import register_post_signup_hook  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_logger.info("Starting application...")
    consumer_connection = None

    # ── Sentry ────────────────────────────────────────────────────────
    if settings.SENTRY_DSN:
        init_sentry(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        )

    # ── Scheduler ─────────────────────────────────────────────────────
    if settings.ENABLE_SCHEDULER:
        app_logger.info("Starting scheduler...")
        scheduler.start()
        initialize_scheduler()
        app_logger.info("Scheduler started.")
    else:
        app_logger.info("Scheduler disabled.")

    # ── Messaging ─────────────────────────────────────────────────────
    if settings.ENABLE_RABBITMQ_CONSUMERS:
        app_logger.info("Starting message consumers...")
        consumer_connection = await start_consumers(keep_alive=False)
        register_publisher(publish_event)
        app_logger.info("Message consumers started.")
    else:
        app_logger.info("Messaging disabled.")

    # ── Post-signup hooks ─────────────────────────────────────────────
    # Register hooks here. Example:
    # register_post_signup_hook(my_setup_callback)

    # TODO: Initialize additional services (Redis, email, OAuth, etc.)

    app_logger.info("Application startup complete.")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────
    app_logger.info("Shutting down application...")

    if consumer_connection:
        await consumer_connection.close()

    if settings.ENABLE_SCHEDULER and scheduler.running:
        scheduler.shutdown()

    app_logger.info("Application shutdown complete.")


app = FastAPI(
    lifespan=lifespan,
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    debug=settings.DEBUG,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    responses=exception_schema,
    root_path_in_servers=False,
    servers=[{"url": settings.API_DOMAIN}],
)

# ── Exception handlers (order: most specific → generic) ──────────────────
app.add_exception_handler(OTPExpiredException, otp_expired_exception_handler)
app.add_exception_handler(OTPInvalidException, otp_invalid_exception_handler)
app.add_exception_handler(TooManyAttemptsException, too_many_attempts_exception_handler)
app.add_exception_handler(RateLimitExceededException, rate_limit_exception_handler)
app.add_exception_handler(OAuthException, oauth_exception_handler)
app.add_exception_handler(AuthenticationException, authentication_exception_handler)
app.add_exception_handler(ForbiddenException, forbidden_exception_handler)
app.add_exception_handler(PaymentRequiredException, payment_required_exception_handler)
app.add_exception_handler(NotFoundException, not_found_exception_handler)
app.add_exception_handler(ConflictException, conflict_exception_handler)
app.add_exception_handler(BadRequestException, bad_request_exception_handler)
app.add_exception_handler(DatabaseException, database_exception_handler)
app.add_exception_handler(NotImplementedException, not_implemented_exception_handler)
app.add_exception_handler(ValueError, value_error_exception_handler)
app.add_exception_handler(AppException, general_exception_handler)

# ── Middleware ────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    session_cookie=settings.SESSION_COOKIE_NAME,
    https_only=not settings.DEBUG,
    same_site=settings.SESSION_SAME_SITE_COOKIE_POLICY,
)

# ── Routers ──────────────────────────────────────────────────────────────
app.include_router(item_router, prefix="/api", tags=["Items"])
# TODO: Add your auth, webhook, and domain routers here.

# ── Admin ─────────────────────────────────────────────────────────────────
init_admin(app)


# ── Root & health ────────────────────────────────────────────────────────


@app.get("/", include_in_schema=False)
async def root(request: Request):
    base_url = request.base_url._url.rstrip("/")
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "docs": {
            "swagger": f"{base_url}/docs",
            "redoc": f"{base_url}/redoc",
        },
        "version": settings.APP_VERSION,
    }


@app.head("/health", include_in_schema=False)
@app.get("/health")
async def health_check(session: Annotated[AsyncSession, Depends(get_async_session)]):
    """Health check — verifies database connectivity."""
    health_status = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "checks": {"database": "ok"},
    }

    try:
        async with session.begin():
            result = await session.execute(text("SELECT 1"))
            if result.scalar() != 1:
                health_status["checks"]["database"] = "unhealthy"
                health_status["status"] = "degraded"
    except Exception as e:
        app_logger.error(f"Database health check failed: {e}")
        health_status["checks"]["database"] = "unhealthy"
        health_status["status"] = "degraded"

    if health_status["status"] != "healthy":
        raise AppException(
            "One or more health checks failed.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=health_status,
        )

    return health_status
