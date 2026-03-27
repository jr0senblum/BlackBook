"""ActionItemRepository — database access for the action_items table."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import ActionItem


class ActionItemRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        *,
        company_id: UUID,
        description: str,
        source_id: UUID | None = None,
        inferred_fact_id: UUID | None = None,
        person_id: UUID | None = None,
        functional_area_id: UUID | None = None,
    ) -> ActionItem:
        """Insert a new action item row."""
        action_item = ActionItem(
            company_id=company_id,
            description=description,
            source_id=source_id,
            inferred_fact_id=inferred_fact_id,
            person_id=person_id,
            functional_area_id=functional_area_id,
        )
        self._db.add(action_item)
        await self._db.flush()
        await self._db.refresh(action_item)
        return action_item

    async def get_by_id(self, item_id: UUID) -> ActionItem | None:
        """Return an action item by primary key, or None."""
        result = await self._db.execute(
            select(ActionItem).where(ActionItem.id == item_id)
        )
        return result.scalar_one_or_none()
