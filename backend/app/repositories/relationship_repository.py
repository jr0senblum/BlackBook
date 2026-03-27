"""RelationshipRepository — database access for the relationships table."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Relationship


class RelationshipRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        *,
        company_id: UUID,
        subordinate_person_id: UUID,
        manager_person_id: UUID,
        inferred_fact_id: UUID | None = None,
    ) -> Relationship:
        """Insert a new relationship row."""
        relationship = Relationship(
            company_id=company_id,
            subordinate_person_id=subordinate_person_id,
            manager_person_id=manager_person_id,
            inferred_fact_id=inferred_fact_id,
        )
        self._db.add(relationship)
        await self._db.flush()
        await self._db.refresh(relationship)
        return relationship
