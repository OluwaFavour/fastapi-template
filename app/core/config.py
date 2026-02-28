from functools import lru_cache
import logging
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.logger import setup_logger, init_sentry


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    API_DOMAIN: str = "http://localhost:8000"
    APP_NAME: str = "MyApp"  # TODO: Replace with your app name
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = """Your FastAPI application description."""  # TODO: Replace
    DEBUG: bool = False
    ROOT_PATH: str = "/v1"

    # ── CORS ─────────────────────────────────────────────────────────────
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3000"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # ── Session ──────────────────────────────────────────────────────────
    SESSION_COOKIE_NAME: str = "session"
    SESSION_SECRET_KEY: str = "supersecretkey"
    SESSION_SAME_SITE_COOKIE_POLICY: Literal["lax", "strict", "none"] = "lax"

    # ── JWT ───────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "another_supersecret_key"
    JWT_ALGORITHM: str = "HS256"

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str
    TEST_DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"

    # ── Redis ────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Rate limiting ────────────────────────────────────────────────────
    RATE_LIMIT_BACKEND: Literal["memory", "redis"] = "memory"
    RATE_LIMIT_DEFAULT_REQUESTS: int = 100
    RATE_LIMIT_DEFAULT_WINDOW: int = 60  # seconds

    # ── OTP ───────────────────────────────────────────────────────────────
    OTP_LENGTH: int = 6
    OTP_EXPIRY_MINUTES: int = 10
    OTP_HMAC_SECRET: str = "otp_hmac_secret_key_change_in_production"
    OTP_MAX_ATTEMPTS: int = 5

    # ── OAuth (OPTIONAL — remove if not needed) ──────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    OAUTH_REDIRECT_BASE_URI: str = "http://localhost:8000/auth"

    # ── RabbitMQ (OPTIONAL — remove if not using messaging) ──────────────
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672//"
    ENABLE_MESSAGING: bool = True

    # ── Scheduler (OPTIONAL — remove if not using scheduler) ─────────────
    ENABLE_SCHEDULER: bool = True

    # ── Sentry (OPTIONAL — remove if not using error tracking) ───────────
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # ── Internal API ─────────────────────────────────────────────────────
    INTERNAL_API_SECRET: str = "internal_api_secret_change_in_production"

    # ── Admin ────────────────────────────────────────────────────────────
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin_password_change_in_production"
    ADMIN_TOKEN_VERSION: int = 0
    ADMIN_ALERT_EMAIL: str | None = None

    model_config: SettingsConfigDict = SettingsConfigDict(  # type: ignore
        env_file=".env",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _validate_production_secrets(self) -> "Settings":
        """Ensure insecure default secrets are overridden in production."""
        if self.ENVIRONMENT != "production":
            return self

        insecure_defaults: dict[str, str] = {
            "SESSION_SECRET_KEY": "supersecretkey",
            "JWT_SECRET_KEY": "another_supersecret_key",
            "OTP_HMAC_SECRET": "otp_hmac_secret_key_change_in_production",
            "INTERNAL_API_SECRET": "internal_api_secret_change_in_production",
            "ADMIN_PASSWORD": "admin_password_change_in_production",
        }

        still_default = [
            name
            for name, default_val in insecure_defaults.items()
            if getattr(self, name) == default_val
        ]

        if still_default:
            raise ValueError(
                f"ENVIRONMENT is 'production' but the following secrets still "
                f"have their insecure default values: {', '.join(still_default)}. "
                f"Set them via environment variables or .env file."
            )

        if self.RATE_LIMIT_BACKEND == "memory":
            raise ValueError(
                "ENVIRONMENT is 'production' but RATE_LIMIT_BACKEND is 'memory'. "
                "Set it to 'redis' for multi-replica safety."
            )

        return self


@lru_cache()
def get_settings() -> Settings:
    return Settings()  # type: ignore


settings = get_settings()

# Initialize Sentry once globally
if not settings.DEBUG:
    init_sentry(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
    )

# ── Domain loggers ───────────────────────────────────────────────────────
# Add or remove loggers as needed for your project's domains.
app_logger = setup_logger(
    name="app_logger",
    log_file="logs/app.log",
    level=logging.INFO,
    sentry_tag="app",
)
database_logger = setup_logger(
    name="database_logger",
    log_file="logs/database.log",
    level=logging.INFO,
    sentry_tag="database",
)
request_logger = setup_logger(
    name="request_logger",
    log_file="logs/requests.log",
    level=logging.INFO,
    sentry_tag="request",
)
rabbitmq_logger = setup_logger(
    name="rabbitmq_logger",
    log_file="logs/rabbitmq.log",
    level=logging.INFO,
    sentry_tag="messaging",
)
scheduler_logger = setup_logger(
    name="scheduler_logger",
    log_file="logs/scheduler.log",
    level=logging.INFO,
    sentry_tag="scheduler",
)
auth_logger = setup_logger(
    name="auth_logger",
    log_file="logs/auth.log",
    level=logging.INFO,
    sentry_tag="auth",
)
redis_logger = setup_logger(
    name="redis_logger",
    log_file="logs/redis.log",
    level=logging.INFO,
    sentry_tag="redis",
)

__all__ = [
    "settings",
    "app_logger",
    "database_logger",
    "request_logger",
    "rabbitmq_logger",
    "scheduler_logger",
    "auth_logger",
    "redis_logger",
]
