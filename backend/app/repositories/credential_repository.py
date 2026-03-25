"""CredentialRepository — database access for the credentials table."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Credential


class CredentialRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_credential(self) -> Credential | None:
        """Return the single credential row, or None if not yet set."""
        result = await self._db.execute(select(Credential).where(Credential.id == 1))
        return result.scalar_one_or_none()

    async def create_credential(self, username: str, password_hash: str) -> Credential:
        """Insert the initial credential row (id=1)."""
        credential = Credential(id=1, username=username, password_hash=password_hash)
        self._db.add(credential)
        await self._db.flush()
        return credential

    async def update_password_hash(self, password_hash: str) -> Credential:
        """Update the password hash on the existing credential row."""
        result = await self._db.execute(select(Credential).where(Credential.id == 1))
        credential = result.scalar_one()
        credential.password_hash = password_hash
        await self._db.flush()
        return credential
