"""SessionRepository — database access for the sessions table."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Session


class SessionRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create_session(self, token: str) -> Session:
        """Insert a new session row."""
        session = Session(token=token)
        self._db.add(session)
        await self._db.flush()
        return session

    async def get_by_token(self, token: str) -> Session | None:
        """Return the session with this token, or None."""
        result = await self._db.execute(select(Session).where(Session.token == token))
        return result.scalar_one_or_none()

    async def update_last_active(self, token: str) -> None:
        """Touch last_active_at to now for the given session."""
        result = await self._db.execute(select(Session).where(Session.token == token))
        session = result.scalar_one()
        session.last_active_at = datetime.now(timezone.utc)
        await self._db.flush()

    async def delete_by_token(self, token: str) -> None:
        """Delete a session by token."""
        await self._db.execute(delete(Session).where(Session.token == token))
        await self._db.flush()

    async def delete_expired(self, timeout_minutes: int) -> int:
        """Delete all sessions older than timeout. Returns count deleted."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
        result = await self._db.execute(
            delete(Session).where(Session.last_active_at < cutoff)
        )
        await self._db.flush()
        return result.rowcount
