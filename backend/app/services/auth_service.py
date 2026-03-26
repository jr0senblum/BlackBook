"""AuthService — authentication, session management, password operations."""

import secrets
from datetime import datetime, timedelta, timezone

import bcrypt

from app.config import Settings
from app.exceptions import (
    CredentialsAlreadySetError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    SessionExpiredError,
    UnauthenticatedError,
)
from app.repositories.credential_repository import CredentialRepository
from app.repositories.session_repository import SessionRepository


class AuthService:
    def __init__(
        self,
        credential_repo: CredentialRepository,
        session_repo: SessionRepository,
        settings: Settings,
    ):
        self._credential_repo = credential_repo
        self._session_repo = session_repo
        self._settings = settings

    async def set_password(self, username: str, password: str) -> None:
        """Set password on first access. Fails with 409 if already set."""
        existing = await self._credential_repo.get_credential()
        if existing is not None:
            raise CredentialsAlreadySetError()
        password_hash = self._hash_password(password)
        await self._credential_repo.create_credential(username, password_hash)

    async def login(self, username: str, password: str) -> str:
        """Validate credentials and create a session. Returns the session token."""
        credential = await self._credential_repo.get_credential()
        if credential is None:
            raise InvalidCredentialsError()
        if credential.username != username:
            raise InvalidCredentialsError()
        if not self._verify_password(password, credential.password_hash):
            raise InvalidCredentialsError()
        token = secrets.token_hex(32)
        await self._session_repo.create_session(token)
        return token

    async def logout(self, token: str) -> None:
        """Delete the session."""
        await self._session_repo.delete_by_token(token)

    async def change_password(self, token: str, current_password: str, new_password: str) -> None:
        """Change password. Validates current password first."""
        credential = await self._credential_repo.get_credential()
        if credential is None or not self._verify_password(current_password, credential.password_hash):
            raise InvalidCurrentPasswordError()
        new_hash = self._hash_password(new_password)
        await self._credential_repo.update_password_hash(new_hash)

    async def validate_session(self, token: str | None) -> None:
        """Validate that the token represents an active, non-expired session.

        Updates last_active_at on success. Raises UnauthenticatedError on failure.
        """
        if token is None:
            raise UnauthenticatedError()
        session = await self._session_repo.get_by_token(token)
        if session is None:
            raise UnauthenticatedError()
        now = datetime.now(timezone.utc)
        timeout = timedelta(minutes=self._settings.session_timeout_minutes)
        if now - session.last_active_at > timeout:
            # Session expired — delete it and reject
            await self._session_repo.delete_by_token(token)
            raise SessionExpiredError()
        # Session is valid — touch last_active_at
        await self._session_repo.update_last_active(token)

    @staticmethod
    def _hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
