"""InferredFactRepository — database access for the inferred_facts table."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import InferredFact


class InferredFactRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create_many(self, facts: list[dict]) -> list[InferredFact]:
        """Bulk insert inferred fact rows.

        Each dict in ``facts`` must contain keys matching InferredFact columns
        (at minimum: source_id, company_id, category, inferred_value).
        """
        rows = []
        for fact_data in facts:
            row = InferredFact(**fact_data)
            self._db.add(row)
            rows.append(row)
        await self._db.flush()
        for row in rows:
            await self._db.refresh(row)
        return rows

    async def exists_by_value(
        self,
        company_id: UUID,
        category: str,
        inferred_value: str,
    ) -> bool:
        """Return True if a non-dismissed fact with this (company, category, value) exists.

        Matches case-insensitively.  Used to skip duplicate facts when the same
        source is uploaded twice.
        """
        result = await self._db.execute(
            select(func.count())
            .select_from(InferredFact)
            .where(
                InferredFact.company_id == company_id,
                InferredFact.category == category,
                func.lower(InferredFact.inferred_value) == inferred_value.lower(),
                InferredFact.status.in_(("pending", "accepted", "corrected", "merged")),
            )
        )
        return result.scalar_one() > 0

    async def get_by_id(self, fact_id: UUID) -> InferredFact | None:
        """Return an inferred fact by primary key, or None."""
        result = await self._db.execute(
            select(InferredFact).where(InferredFact.id == fact_id)
        )
        return result.scalar_one_or_none()

    async def list_by_company(
        self,
        company_id: UUID,
        *,
        status: str = "pending",
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[InferredFact], int]:
        """Return paginated inferred facts for a company.

        Filters by ``status`` (default 'pending') and optionally ``category``.
        Ordered by created_at ASC.  Returns (items, total).
        """
        base = select(InferredFact).where(
            InferredFact.company_id == company_id,
            InferredFact.status == status,
        )
        count_base = (
            select(func.count())
            .select_from(InferredFact)
            .where(
                InferredFact.company_id == company_id,
                InferredFact.status == status,
            )
        )

        if category is not None:
            base = base.where(InferredFact.category == category)
            count_base = count_base.where(InferredFact.category == category)

        total_result = await self._db.execute(count_base)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base.order_by(InferredFact.created_at.asc()).limit(limit).offset(offset)
        )
        items = list(result.scalars().all())

        return items, total

    async def update_status(
        self,
        fact_id: UUID,
        *,
        status: str,
        reviewed_at: datetime,
        corrected_value: str | None = None,
        merged_into_entity_type: str | None = None,
        merged_into_entity_id: UUID | None = None,
    ) -> InferredFact:
        """Update the status and review fields of an inferred fact.

        ``reviewed_at`` is required — every status transition is a review action.
        Raises ValueError if the fact_id does not exist.
        """
        fact = await self.get_by_id(fact_id)
        if fact is None:
            raise ValueError(f"InferredFact not found: {fact_id}")
        fact.status = status
        fact.reviewed_at = reviewed_at
        fact.corrected_value = corrected_value
        fact.merged_into_entity_type = merged_into_entity_type
        fact.merged_into_entity_id = merged_into_entity_id
        await self._db.flush()
        await self._db.refresh(fact)
        return fact
