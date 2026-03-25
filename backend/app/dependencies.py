"""FastAPI dependency providers."""

from collections.abc import AsyncGenerator

from fastapi import Cookie, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.exceptions import UnauthenticatedError
from app.repositories.credential_repository import CredentialRepository
from app.repositories.session_repository import SessionRepository
from app.services.auth_service import AuthService

# Database engine and session factory — created once at import time.
engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session per request."""
    async with async_session_factory() as session:
        async with session.begin():
            yield session


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """Provide an AuthService instance."""
    return AuthService(
        credential_repo=CredentialRepository(db),
        session_repo=SessionRepository(db),
        settings=settings,
    )


async def get_current_session(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> str:
    """Validate the session cookie. Returns the session token on success.

    Raises UnauthenticatedError (401) if the cookie is missing, invalid, or expired.
    """
    token = request.cookies.get("session")
    await auth_service.validate_session(token)
    return token
