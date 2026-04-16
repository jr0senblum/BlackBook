"""InferredFactRepository — database access for the inferred_facts table."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select, union_all
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

    async def list_accepted_by_company(
        self,
        company_id: UUID,
        *,
        limit: int = 500,
    ) -> list[InferredFact]:
        """Return accepted/corrected facts for a company, newest first.

        Used by context assembly to build company context for the LLM.
        The ``limit`` caps the query to prevent loading unbounded rows;
        the caller enforces the character budget.
        """
        result = await self._db.execute(
            select(InferredFact)
            .where(
                InferredFact.company_id == company_id,
                InferredFact.status.in_(("accepted", "corrected")),
            )
            .order_by(InferredFact.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

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

    async def list_linked_to_person(
        self,
        company_id: UUID,
        person_id: UUID,
        person_name: str,
        primary_area_id: UUID | None,
    ) -> list[InferredFact]:
        """Return accepted/corrected facts linked to a person.

        # DECISION: this method returns the union of two sets beyond what §10.5
        # specifies (area-linked facts only).  It also includes facts where
        # inferred_value contains the person's name (case-insensitive contains
        # match, category = 'person').  Rationale: without name-matched facts,
        # the investigator visiting a person detail page would not see the
        # original fact(s) that sourced this person.  The extension is additive —
        # area facts still appear.  No downstream consequences beyond showing
        # more facts on the detail page.

        Set 1: accepted/corrected person-category facts whose inferred_value
               contains person_name (case-insensitive).
        Set 2: accepted/corrected facts of any category whose functional_area_id
               matches primary_area_id (only when primary_area_id is not None).

        The two sets are unioned, deduplicated by fact ID, and ordered by
        created_at ascending.
        """
        base_filters = [
            InferredFact.company_id == company_id,
            InferredFact.status.in_(("accepted", "corrected")),
        ]

        # Set 1: person facts whose inferred_value mentions the person's name
        name_query = (
            select(InferredFact)
            .where(
                *base_filters,
                InferredFact.category == "person",
                func.lower(InferredFact.inferred_value).contains(
                    person_name.lower()
                ),
            )
        )

        if primary_area_id is not None:
            # Set 2: facts tagged to the person's primary area
            area_query = (
                select(InferredFact)
                .where(
                    *base_filters,
                    InferredFact.functional_area_id == primary_area_id,
                )
            )
            # Union both sets and deduplicate by ID via a subquery
            combined = union_all(name_query, area_query).subquery()
            # Re-select as ORM objects, deduplicate by id, order by created_at
            result = await self._db.execute(
                select(InferredFact)
                .where(InferredFact.id.in_(select(combined.c.id)))
                .order_by(InferredFact.created_at.asc())
            )
        else:
            result = await self._db.execute(
                name_query.order_by(InferredFact.created_at.asc())
            )

        return list(result.scalars().all())

    async def update_corrected_value(
        self,
        fact_id: UUID,
        corrected_value: str,
    ) -> InferredFact:
        """Set corrected_value on a fact without changing status.

        Used by UC 17 (update_fact_value) to edit an already-accepted or
        corrected fact in place.  The original ``inferred_value`` is never
        overwritten per §6.3.
        """
        fact = await self.get_by_id(fact_id)
        if fact is None:
            raise ValueError(f"InferredFact not found: {fact_id}")
        fact.corrected_value = corrected_value
        await self._db.flush()
        await self._db.refresh(fact)
        return fact

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
