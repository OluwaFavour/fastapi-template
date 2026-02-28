"""
Pytest configuration and core fixtures.

Provides fixtures for integration tests using a real test database with per-test rollback.
All fixtures are function-scoped for complete test isolation.
"""

# Ensure ALL SQLAlchemy models are registered before any mapper configuration.
import app.core.db.models  # noqa: F401
import app.apps.example_app.db.models  # noqa: F401

import os
from datetime import timedelta
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
)


def create_test_access_token(user) -> str:
    """Create a test access token for a user."""
    from app.core.utils import create_jwt_token

    return create_jwt_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "type": "access",
        },
        expires_delta=timedelta(minutes=15),
    )


def pytest_configure(config):
    """Configure pytest with custom settings."""
    os.environ["ENVIRONMENT"] = "test"

    test_db_url = os.environ.get("TEST_DATABASE_URL")
    if test_db_url:
        os.environ["DATABASE_URL"] = test_db_url

    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (require real database)",
    )


# ---------------------------------------------------------------------------
# Singleton resets
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset all singleton service state after each test for full isolation."""
    yield

    from app.core import logger as logger_module

    logger_module._sentry_initialized = False

    from app.core.services.event_publisher import reset_publisher

    reset_publisher()

    from app.core.services.lifecycle import reset_hooks

    reset_hooks()

    # TODO: Add resets for any additional SingletonService subclasses.


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use the default event loop policy for the session."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database(event_loop_policy):
    """Run Alembic migrations at session start and truncate tables at end."""
    import asyncio
    import subprocess
    import sys

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine as _create_engine

    from app.core.config import settings

    if not settings.TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not configured")

    original_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = settings.TEST_DATABASE_URL

    try:
        print("\n[TEST] Running database migrations for test database...")
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        if result.returncode != 0:
            print(f"[TEST] Migration failed: {result.stderr}")
            pytest.fail(f"Database migration failed: {result.stderr}")
        else:
            print("[TEST] Database migrations completed successfully")

        yield settings.TEST_DATABASE_URL

        # Cleanup: truncate all tables after tests
        print("\n[TEST] Cleaning up test database...")

        async def cleanup_database():
            engine = _create_engine(settings.TEST_DATABASE_URL, echo=False)
            preserved_tables = {"alembic_version"}

            async with engine.begin() as conn:
                result = await conn.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                )
                all_tables = [row[0] for row in result.fetchall()]
                tables = [t for t in all_tables if t not in preserved_tables]

                if tables:
                    table_list = ", ".join(f'"{t}"' for t in tables)
                    await conn.execute(
                        text(f"TRUNCATE TABLE {table_list} RESTART IDENTITY CASCADE")
                    )
                    print(f"[TEST] Truncated {len(tables)} tables")

            await engine.dispose()

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(cleanup_database())
        finally:
            loop.close()

        print("[TEST] Test database cleanup completed")

    finally:
        if original_database_url is not None:
            os.environ["DATABASE_URL"] = original_database_url
        elif "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session with per-test transaction rollback.

    Strategy:
    1. Start an outer transaction (for final rollback)
    2. Bind a session to that connection
    3. Patch session.begin() -> begin_nested() so app code's ``async with session.begin():``
       creates savepoints instead of real commits
    4. Rollback everything after the test
    """
    from app.core.config import settings

    if not settings.TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not configured")

    engine = create_async_engine(
        settings.TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )

    connection = await engine.connect()
    outer_transaction = await connection.begin()

    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        autobegin=True,
    )

    # Patch begin() -> begin_nested() so router code works inside the outer txn
    session.begin = lambda: session.begin_nested()  # type: ignore[assignment]

    try:
        yield session
    finally:
        await session.close()
        await outer_transaction.rollback()
        await connection.close()
        await engine.dispose()


# ---------------------------------------------------------------------------
# App & client fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Create FastAPI application for testing."""
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture
async def client(app, db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client with session override for test isolation."""
    from app.core.dependencies import get_async_session

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_async_session, None)


# ---------------------------------------------------------------------------
# Mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_email_service():
    """Auto-mock event publisher to prevent real RabbitMQ connections."""
    from app.core.services.event_publisher import register_publisher, reset_publisher

    async def mock_publish_event(*args, **kwargs):
        return None

    register_publisher(mock_publish_event)

    with patch(
        "app.infrastructure.messaging.publisher.publish_event",
        side_effect=mock_publish_event,
    ):
        yield

    reset_publisher()


# ---------------------------------------------------------------------------
# Example data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create a verified, active test user."""
    from app.core.db.models import User

    user = User(
        id=uuid4(),
        email="testuser@example.com",
        hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.vwPbgsgNJwKrWe",
        full_name="Test User",
        is_verified=True,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def auth_headers(test_user):
    """Return Authorization headers for the test user."""
    token = create_test_access_token(test_user)
    return {"Authorization": f"Bearer {token}"}
