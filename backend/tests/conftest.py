"""Fixtures: test DB, test client, per-test savepoint isolation.

Design note — SAVEPOINT rollback is the load-bearing isolation mechanism:

  Test fixtures for repositories, services, and the HTTP client are all
  ``loop_scope="session"`` scoped.  They hold thin wrappers (repos, services)
  around the *same* ``db_session`` instance.  This is safe because:

  1. ``db_session`` opens a connection-level transaction + SAVEPOINT per test.
  2. On teardown the SAVEPOINT (and outer transaction) is rolled back, so every
     test starts with a clean database — regardless of what earlier tests wrote.
  3. The session-scoped repo/service objects carry no cached state; they just
     delegate to ``self._db``.

  If the savepoint rollback in ``db_session`` is ever removed or broken, *all*
  tests will bleed into each other simultaneously, producing an obvious,
  session-wide failure rather than subtle per-file issues.
"""

import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings
from app.dependencies import get_db
from app.main import create_app
from app.models.base import Base

# Test database URL — uses the same local PostgreSQL but a separate database.
TEST_DATABASE_URL = "postgresql+asyncpg://localhost:5432/blackbook_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def setup_database() -> AsyncGenerator[None, None]:
    """Create all tables at session start, drop at session end."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(
    setup_database: None,
) -> AsyncGenerator[AsyncSession, None]:
    """Per-test database session with savepoint isolation.

    Opens a real connection-level transaction, then a SAVEPOINT inside it.
    The session is bound to the connection so all ORM operations run inside
    the savepoint. After the test, the savepoint (and therefore the outer
    transaction) is rolled back — leaving the database unchanged.
    """
    async with test_engine.connect() as conn:
        # Outer transaction — never committed.
        txn = await conn.begin()
        # Bind a session to this connection so it shares the transaction.
        session = AsyncSession(bind=conn, expire_on_commit=False)
        # SAVEPOINT — the test's writes go here.
        await conn.begin_nested()

        yield session

        # Teardown: close session, roll back everything.
        await session.close()
        await txn.rollback()


@pytest_asyncio.fixture(loop_scope="session")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an async HTTP client wired to the test database."""
    app = create_app()

    # Override the database dependency to use the test session.
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as ac:
        yield ac


def get_test_settings() -> Settings:
    """Return settings configured for tests."""
    return Settings(database_url=TEST_DATABASE_URL, session_timeout_minutes=5)
