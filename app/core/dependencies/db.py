from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, closing it after the request."""
    async with AsyncSessionLocal() as async_session:
        yield async_session
