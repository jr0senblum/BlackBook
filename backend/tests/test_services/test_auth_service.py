"""Tests for AuthService."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.exceptions import (
    CredentialsAlreadySetError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    UnauthenticatedError,
)
from app.repositories.credential_repository import CredentialRepository
from app.repositories.session_repository import SessionRepository
from app.services.auth_service import AuthService
from tests.conftest import get_test_settings

USERNAME = "investigator"
PASSWORD = "testpassword123"


@pytest_asyncio.fixture(loop_scope="session")
async def auth_service(db_session: AsyncSession) -> AuthService:
    """Bare AuthService — no credential seeded."""
    return AuthService(
        credential_repo=CredentialRepository(db_session),
        session_repo=SessionRepository(db_session),
        settings=get_test_settings(),
    )


@pytest_asyncio.fixture(loop_scope="session")
async def seeded_auth_service(auth_service: AuthService) -> AuthService:
    """AuthService with the default credential already created."""
    await auth_service.set_password(USERNAME, PASSWORD)
    return auth_service


# ── set_password ─────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_set_password(auth_service: AuthService) -> None:
    """First call succeeds."""
    await auth_service.set_password(USERNAME, PASSWORD)


@pytest.mark.asyncio(loop_scope="session")
async def test_set_password_idempotency(auth_service: AuthService) -> None:
    """Second call to set_password after first raises CredentialsAlreadySetError."""
    # Ensure credential exists first.
    await auth_service.set_password(USERNAME, PASSWORD)
    with pytest.raises(CredentialsAlreadySetError):
        await auth_service.set_password(USERNAME, "anotherpassword")


# ── login ────────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_login_success(seeded_auth_service: AuthService) -> None:
    """Login with correct credentials returns a token."""
    token = await seeded_auth_service.login(USERNAME, PASSWORD)
    assert isinstance(token, str)
    assert len(token) == 64  # 32 bytes = 64 hex chars


@pytest.mark.asyncio(loop_scope="session")
async def test_login_wrong_username(seeded_auth_service: AuthService) -> None:
    """Login with wrong username raises InvalidCredentialsError."""
    with pytest.raises(InvalidCredentialsError):
        await seeded_auth_service.login("wrong_user", PASSWORD)


@pytest.mark.asyncio(loop_scope="session")
async def test_login_wrong_password(seeded_auth_service: AuthService) -> None:
    """Login with wrong password raises InvalidCredentialsError."""
    with pytest.raises(InvalidCredentialsError):
        await seeded_auth_service.login(USERNAME, "wrongpassword")


# ── validate_session ─────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_validate_session_success(seeded_auth_service: AuthService) -> None:
    """Valid session token passes validation."""
    token = await seeded_auth_service.login(USERNAME, PASSWORD)
    # Should not raise
    await seeded_auth_service.validate_session(token)


@pytest.mark.asyncio(loop_scope="session")
async def test_validate_session_none(auth_service: AuthService) -> None:
    """None token raises UnauthenticatedError."""
    with pytest.raises(UnauthenticatedError):
        await auth_service.validate_session(None)


@pytest.mark.asyncio(loop_scope="session")
async def test_validate_session_invalid_token(auth_service: AuthService) -> None:
    """Non-existent token raises UnauthenticatedError."""
    with pytest.raises(UnauthenticatedError):
        await auth_service.validate_session("nonexistent_token")


@pytest.mark.asyncio(loop_scope="session")
async def test_validate_session_expired(db_session: AsyncSession) -> None:
    """Expired session raises UnauthenticatedError."""
    expired_settings = Settings(database_url="unused", session_timeout_minutes=0)
    service = AuthService(
        credential_repo=CredentialRepository(db_session),
        session_repo=SessionRepository(db_session),
        settings=expired_settings,
    )
    # Seed credential within this session so login works.
    await service.set_password(USERNAME, PASSWORD)
    token = await service.login(USERNAME, PASSWORD)
    with pytest.raises(UnauthenticatedError):
        await service.validate_session(token)


# ── logout ───────────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_logout(seeded_auth_service: AuthService) -> None:
    """After logout, the session token is invalid."""
    token = await seeded_auth_service.login(USERNAME, PASSWORD)
    await seeded_auth_service.logout(token)
    with pytest.raises(UnauthenticatedError):
        await seeded_auth_service.validate_session(token)


# ── change_password ──────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_change_password_success(seeded_auth_service: AuthService) -> None:
    """Changing password with correct current password succeeds."""
    token = await seeded_auth_service.login(USERNAME, PASSWORD)
    await seeded_auth_service.change_password(token, PASSWORD, "newpassword456")
    # Verify login works with new password
    new_token = await seeded_auth_service.login(USERNAME, "newpassword456")
    assert isinstance(new_token, str)
    # Change back so other tests still work
    await seeded_auth_service.change_password(new_token, "newpassword456", PASSWORD)


@pytest.mark.asyncio(loop_scope="session")
async def test_change_password_wrong_current(seeded_auth_service: AuthService) -> None:
    """Wrong current password raises InvalidCurrentPasswordError."""
    token = await seeded_auth_service.login(USERNAME, PASSWORD)
    with pytest.raises(InvalidCurrentPasswordError):
        await seeded_auth_service.change_password(token, "wrongcurrent", "newpassword456")
