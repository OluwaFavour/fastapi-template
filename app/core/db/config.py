from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    async_sessionmaker,
    AsyncAttrs,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

ASYNC_SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

async_engine: AsyncEngine = create_async_engine(
    ASYNC_SQLALCHEMY_DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    autoflush=False,
    expire_on_commit=False,
    autobegin=True,
)


class Base(AsyncAttrs, DeclarativeBase):
    pass


async def init_db() -> None:
    """Create all tables defined in the metadata."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    """Dispose the database connection."""
    await async_engine.dispose()
