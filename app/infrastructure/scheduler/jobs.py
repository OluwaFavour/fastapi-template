"""Scheduled jobs — add your recurring tasks here."""

from datetime import datetime, timedelta, timezone

from app.core.config import scheduler_logger
from app.core.db import AsyncSessionLocal
from app.core.db.crud import user_db


async def cleanup_soft_deleted_users(days_threshold: int = 30) -> None:
    """Permanently delete users that were soft-deleted more than `days_threshold` days ago."""
    scheduler_logger.info(
        f"Running cleanup_soft_deleted_users (threshold={days_threshold} days)"
    )
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_threshold)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            count = await user_db.permanently_delete_soft_deleted(
                session, cutoff_date=cutoff, commit_self=False
            )

    scheduler_logger.info(f"Permanently deleted {count} soft-deleted user(s).")
