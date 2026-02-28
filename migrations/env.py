import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy import pool

from alembic import context

from app.core.db import Base

# Import all models so Alembic can detect them for autogenerate.
from app.core.db.models import *  # noqa: F401, F403
from app.apps.example_app.db.models import *  # noqa: F401, F403

from app.core.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_name(name: str, type_: str, parent_names: list[str]) -> bool:
    """Exclude APScheduler internal tables from autogenerate."""
    if type_ == "table" and name.startswith("scheduler_"):
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: AsyncConnection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_name=include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode with an async engine."""
    connectable = create_async_engine(
        url=settings.DATABASE_URL, poolclass=pool.NullPool
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
