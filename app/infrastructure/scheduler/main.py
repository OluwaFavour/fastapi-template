"""Scheduler Module.

Standalone usage::

    python -m app.infrastructure.scheduler.main

Docker::

    docker compose --profile scheduler-only up -d
"""

import asyncio
import logging
import signal
from datetime import timezone

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import scheduler_logger, settings

logging.basicConfig(level=logging.INFO)
logging.getLogger("apscheduler").setLevel(logging.DEBUG)


def _sync_database_url() -> str:
    """Convert the async DATABASE_URL to a synchronous one for APScheduler.

    Only modifies the driver scheme so the rest of the URL — including any
    percent-encoded password — is preserved exactly.
    """
    scheme, rest = settings.DATABASE_URL.split("://", 1)
    return f"{scheme.replace('+asyncpg', '')}://{rest}"


_sync_url = _sync_database_url()

scheduler = AsyncIOScheduler(
    jobstores={
        "default": SQLAlchemyJobStore(
            url=_sync_url,
            tablename="scheduler_jobs",
        ),
    },
    timezone=timezone.utc,
)


def schedule_cleanup_soft_deleted_users_job(days_threshold: int = 30) -> None:
    """Schedule the soft-deleted user cleanup job (daily at 3:00 AM UTC)."""
    from app.infrastructure.scheduler.jobs import cleanup_soft_deleted_users

    scheduler_logger.info(
        "Scheduling 'cleanup_soft_deleted_users' job to run daily at 3:00 AM UTC"
    )
    scheduler.add_job(
        cleanup_soft_deleted_users,
        trigger=CronTrigger(hour=3, minute=0, timezone=timezone.utc),
        replace_existing=True,
        id="cleanup_soft_deleted_users_job",
        jobstore="default",
        misfire_grace_time=60 * 60,
        kwargs={"days_threshold": days_threshold},
    )


def initialize_scheduler() -> None:
    """Register all scheduled jobs. Call during application startup."""
    schedule_cleanup_soft_deleted_users_job(days_threshold=30)
    # TODO: Add more scheduled jobs here.


async def main() -> None:
    """Main entry point for standalone scheduler execution."""
    shutdown_event = asyncio.Event()

    def handle_shutdown(signum, frame):
        scheduler_logger.info(f"Received signal {signum}, initiating shutdown...")
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    scheduler_logger.info("Starting standalone scheduler...")

    try:
        # TODO: Initialize additional services (Redis, email, etc.) as needed.

        scheduler.start()
        scheduler_logger.info("Scheduler started. Registering jobs...")
        initialize_scheduler()
        await shutdown_event.wait()

    except Exception as e:
        scheduler_logger.exception(f"Scheduler error: {e}")
        raise

    finally:
        scheduler_logger.info("Shutting down scheduler...")
        if scheduler.running:
            scheduler.shutdown(wait=True)
        scheduler_logger.info("Scheduler shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
