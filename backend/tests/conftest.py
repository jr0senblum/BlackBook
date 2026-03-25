"""Fixtures: test DB, test client, service mocks."""

import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.dependencies import get_db
from app.main import create_app
from app.models.base import Base

# Test database URL — uses the same local PostgreSQL but a separate database.
TEST_DATABASE_URL = "postgresql+asyncpg://localhost:5432/blackbook_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)


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


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(setup_database: None) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional database session that rolls back after each test."""
    async with test_session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


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


@pytest_asyncio.fixture(loop_scope="session")
async def authenticated_client(client: AsyncClient) -> AsyncClient:
    """Provide a client with a valid session cookie.

    Sets the password and logs in first.
    """
    # Set password (may already be set from another test — ignore 409)
    await client.post(
        "/api/v1/auth/password/set",
        json={"username": "investigator", "password": "testpassword123"},
    )
    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "investigator", "password": "testpassword123"},
    )
    assert response.status_code == 200
    # The session cookie is now stored on the client
    return client


def get_test_settings() -> Settings:
    """Return settings configured for tests."""
    return Settings(database_url=TEST_DATABASE_URL, session_timeout_minutes=5)
