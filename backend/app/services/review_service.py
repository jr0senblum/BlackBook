"""ReviewService — owns the InferredFact lifecycle.

Responsibilities:
  - save_facts: persist LLM-extracted facts as pending InferredFact rows
  - list_pending: return paginated facts (filterable by status and category)
  - accept_fact: transition a pending fact to accepted, creating entities as needed
  - dismiss_fact: transition a pending fact to dismissed
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.exceptions import (
    FactCompanyMismatchError,
    FactNotFoundError,
    FactNotPendingError,
)
from app.repositories.action_item_repository import ActionItemRepository
from app.repositories.functional_area_repository import FunctionalAreaRepository
from app.repositories.inferred_fact_repository import InferredFactRepository
from app.repositories.person_repository import PersonRepository
from app.repositories.relationship_repository import RelationshipRepository
from app.repositories.source_repository import SourceRepository

if TYPE_CHECKING:
    from app.schemas.inferred_fact import LLMInferredFact

logger = logging.getLogger(__name__)


class ReviewService:
    def __init__(
        self,
        *,
        inferred_fact_repo: InferredFactRepository,
        source_repo: SourceRepository,
        person_repo: PersonRepository,
        functional_area_repo: FunctionalAreaRepository,
        action_item_repo: ActionItemRepository,
        relationship_repo: RelationshipRepository,
    ):
        self._inferred_fact_repo = inferred_fact_repo
        self._source_repo = source_repo
        self._person_repo = person_repo
        self._functional_area_repo = functional_area_repo
        self._action_item_repo = action_item_repo
        self._relationship_repo = relationship_repo

    # ── Save facts from ingestion ───────────────────────────────

    async def save_facts(
        self,
        source_id: str | UUID,
        company_id: str | UUID,
        facts: list[LLMInferredFact],
    ) -> None:
        """Convert LLMInferredFact list to inferred_facts rows (status='pending').

        For relationship facts, inferred_value is stored as "subordinate > manager"
        for reliable re-parsing at accept time.

        Accepts str or UUID for source_id/company_id — converts to UUID internally.
        """
        sid = UUID(str(source_id))
        cid = UUID(str(company_id))
        rows: list[dict[str, Any]] = []
        for fact in facts:
            if fact.category == "relationship":
                # Store as "subordinate > manager" for reliable re-parsing
                inferred_value = f"{fact.subordinate} > {fact.manager}"
            else:
                inferred_value = fact.value

            rows.append({
                "source_id": sid,
                "company_id": cid,
                "category": fact.category,
                "inferred_value": inferred_value,
            })

        if rows:
            await self._inferred_fact_repo.create_many(rows)

    # ── List pending / reviewed facts ───────────────────────────

    async def list_pending(
        self,
        company_id: str,
        *,
        status: str = "pending",
        category: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return paginated facts with source excerpts.

        Returns a tuple of (items, total) where each item is a dict suitable
        for constructing a PendingFactItem schema.
        """
        cid = UUID(company_id)
        facts, total = await self._inferred_fact_repo.list_by_company(
            cid,
            status=status,
            category=category,
            limit=limit,
            offset=offset,
        )

        items: list[dict[str, Any]] = []
        for fact in facts:
            # Get source excerpt (first 200 chars of raw_content)
            source = await self._source_repo.get_by_id(fact.source_id)
            source_excerpt = ""
            if source is not None:
                source_excerpt = (source.raw_content or "")[:200]

            items.append({
                "fact_id": fact.id,
                "category": fact.category,
                "inferred_value": fact.inferred_value,
                "status": fact.status,
                "source_id": fact.source_id,
                "source_excerpt": source_excerpt,
                "candidates": [],  # Phase 2: always empty; Phase 3 adds disambiguation
            })

        return items, total

    # ── Accept a pending fact ────────────────────────────────────

    async def accept_fact(
        self, company_id: str, fact_id: str
    ) -> str | None:
        """Accept a pending fact, creating entities as needed.

        Returns the entity_id (str) of the created entity, or None for
        categories that create no entity.
        """
        cid = UUID(company_id)
        fid = UUID(fact_id)

        fact = await self._inferred_fact_repo.get_by_id(fid)
        if fact is None:
            raise FactNotFoundError(f"Inferred fact not found: {fact_id}")
        if fact.company_id != cid:
            raise FactCompanyMismatchError(
                f"Fact {fact_id} does not belong to company {company_id}"
            )
        if fact.status != "pending":
            raise FactNotPendingError(
                f"Fact status is '{fact.status}', not 'pending'"
            )

        entity_id: str | None = None

        if fact.category == "person":
            entity_id = await self._accept_person(cid, fact)
        elif fact.category == "functional-area":
            entity_id = await self._accept_functional_area(cid, fact)
        elif fact.category == "action-item":
            entity_id = await self._accept_action_item(cid, fact)
        elif fact.category == "relationship":
            entity_id = await self._accept_relationship(cid, fact)
        # All other categories (technology, process, cgkra-*, swot-*, other):
        # no entity creation — just mark accepted.

        # Mark the fact as accepted
        now = datetime.now(timezone.utc)
        await self._inferred_fact_repo.update_status(
            fid, status="accepted", reviewed_at=now
        )

        return entity_id

    # ── Dismiss a pending fact ──────────────────────────────────

    async def dismiss_fact(
        self, company_id: str, fact_id: str
    ) -> None:
        """Dismiss a pending fact."""
        cid = UUID(company_id)
        fid = UUID(fact_id)

        fact = await self._inferred_fact_repo.get_by_id(fid)
        if fact is None:
            raise FactNotFoundError(f"Inferred fact not found: {fact_id}")
        if fact.company_id != cid:
            raise FactCompanyMismatchError(
                f"Fact {fact_id} does not belong to company {company_id}"
            )
        if fact.status != "pending":
            raise FactNotPendingError(
                f"Fact status is '{fact.status}', not 'pending'"
            )

        now = datetime.now(timezone.utc)
        await self._inferred_fact_repo.update_status(
            fid, status="dismissed", reviewed_at=now
        )

    # ── Private accept handlers ─────────────────────────────────

    async def _accept_person(self, company_id: UUID, fact: Any) -> str:
        """Parse inferred_value as "name, title" and create a person."""
        value = fact.inferred_value
        if "," in value:
            # Split on first comma: left = name, right = title
            name, title = value.split(",", 1)
            name = name.strip()
            title = title.strip()
        else:
            name = value.strip()
            title = None

        person = await self._person_repo.create(
            company_id=company_id,
            name=name,
            title=title,
        )
        return str(person.id)

    async def _accept_functional_area(
        self, company_id: UUID, fact: Any
    ) -> str:
        """Create a functional area, or reuse existing if name matches."""
        name = fact.inferred_value.strip()

        # Check for existing (handles UNIQUE constraint on (company_id, name))
        existing = await self._functional_area_repo.get_by_name_iexact(
            company_id, name
        )
        if existing is not None:
            return str(existing.id)

        area = await self._functional_area_repo.create(
            company_id=company_id, name=name
        )
        return str(area.id)

    async def _accept_action_item(
        self, company_id: UUID, fact: Any
    ) -> str:
        """Create an action item from the fact."""
        action_item = await self._action_item_repo.create(
            company_id=company_id,
            description=fact.inferred_value,
            source_id=fact.source_id,
            inferred_fact_id=fact.id,
        )
        return str(action_item.id)

    async def _accept_relationship(
        self, company_id: UUID, fact: Any
    ) -> str:
        """Parse "subordinate > manager" from inferred_value, resolve names, create relationship."""
        value = fact.inferred_value

        if ">" not in value:
            logger.warning(
                "Relationship fact %s has no '>' separator in inferred_value: %s",
                fact.id,
                value,
            )
            # Fallback: treat entire value as subordinate, no manager
            # This shouldn't happen with well-formed data, but be defensive
            sub_name = value.strip()
            mgr_name = "Unknown"
        else:
            parts = value.split(">", 1)
            sub_name = parts[0].strip()
            mgr_name = parts[1].strip()

        # Resolve subordinate
        sub_id = await self._resolve_person(company_id, sub_name)

        # Resolve manager
        mgr_id = await self._resolve_person(company_id, mgr_name)

        # Create relationship row
        relationship = await self._relationship_repo.create(
            company_id=company_id,
            subordinate_person_id=sub_id,
            manager_person_id=mgr_id,
            inferred_fact_id=fact.id,
        )

        # Set reports_to_person_id on the subordinate
        await self._person_repo.update_reports_to(sub_id, mgr_id)

        return str(relationship.id)

    async def _resolve_person(
        self, company_id: UUID, name: str
    ) -> UUID:
        """Resolve a person name to an ID.

        1. Case-insensitive exact match — exactly one match → use that ID.
        2. Multiple matches → use first (Phase 3 adds fuzzy scoring).
        3. No match → create stub person (name only, title=null).
        """
        matches = await self._person_repo.get_by_name_iexact(company_id, name)
        if matches:
            return matches[0].id

        # No match — create stub person
        person = await self._person_repo.create(
            company_id=company_id,
            name=name,
        )
        return person.id
