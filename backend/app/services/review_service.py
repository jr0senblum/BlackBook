"""ReviewService — owns the InferredFact lifecycle.

Responsibilities:
  - save_facts: persist LLM-extracted facts as pending InferredFact rows
  - list_pending: return paginated facts (filterable by status and category)
  - accept_fact: transition a pending fact to accepted, creating entities as needed
  - dismiss_fact: transition a pending fact to dismissed

Phase 3 refactor: delegates entity creation to PersonService and
FunctionalAreaService per §9.2. ActionItemRepository and
RelationshipRepository remain as direct dependencies (partial §9.2
compliance — ActionItemService extraction deferred).
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
from app.repositories.inferred_fact_repository import InferredFactRepository
from app.repositories.relationship_repository import RelationshipRepository
from app.repositories.source_repository import SourceRepository
from app.services.prefix_parser_service import ParsedLine

if TYPE_CHECKING:
    from app.schemas.inferred_fact import LLMInferredFact
    from app.services.functional_area_service import FunctionalAreaService
    from app.services.person_service import PersonService

logger = logging.getLogger(__name__)


class ReviewService:
    def __init__(
        self,
        *,
        inferred_fact_repo: InferredFactRepository,
        source_repo: SourceRepository,
        person_service: PersonService,
        functional_area_service: FunctionalAreaService,
        action_item_repo: ActionItemRepository,
        relationship_repo: RelationshipRepository,
    ):
        self._inferred_fact_repo = inferred_fact_repo
        self._source_repo = source_repo
        self._person_service = person_service
        self._functional_area_service = functional_area_service
        self._action_item_repo = action_item_repo
        self._relationship_repo = relationship_repo

    # ── Save facts from ingestion ───────────────────────────────

    async def save_facts(
        self,
        source_id: str | UUID,
        company_id: str | UUID,
        facts: list[LLMInferredFact],
        lines: list[ParsedLine] | None = None,
        raw_lines: list[str] | None = None,
    ) -> None:
        """Convert LLMInferredFact list to inferred_facts rows (status='pending').

        For relationship facts, inferred_value is stored as "subordinate > manager"
        for reliable re-parsing at accept time.

        Source line attribution (§9.5): each fact is matched back to its
        originating line via substring match.  The matched line is stored
        as ``source_line`` on the inferred_facts row.

        Attribution priority:
          - If ``lines`` is provided: use ``_match_source_line`` (tagged mode).
          - If ``raw_lines`` is provided: use ``_match_raw_source_line`` (raw mode).
          - If both are provided (hybrid): try tagged first, fall back to raw.
          - If neither: ``source_line`` is null.

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

            # Dedup: skip if a non-dismissed fact with the same
            # (company, category, value) already exists.
            already_exists = await self._inferred_fact_repo.exists_by_value(
                cid, fact.category, inferred_value
            )
            if already_exists:
                logger.info(
                    "Skipping duplicate fact: category=%s value=%s",
                    fact.category,
                    inferred_value[:80],
                )
                continue

            # Source line attribution: try tagged match first, fall back to raw
            source_line: str | None = None
            if lines is not None:
                source_line = self._match_source_line(fact, lines)
            if source_line is None and raw_lines is not None:
                source_line = self._match_raw_source_line(fact, raw_lines)

            rows.append({
                "source_id": sid,
                "company_id": cid,
                "category": fact.category,
                "inferred_value": inferred_value,
                "source_line": source_line,
            })

        if rows:
            await self._inferred_fact_repo.create_many(rows)

    @staticmethod
    def _match_source_line(
        fact: LLMInferredFact, lines: list[ParsedLine]
    ) -> str | None:
        """Find the originating ParsedLine for a fact (best-effort).

        Matching strategy per §9.5:
        - For relationship facts: match against subordinate or manager name.
        - For all others: match against fact.value.
        - Substring match, case-insensitive.
        - First match wins (order-preserving from original document).
        - Returns formatted as "canonical_key: text", or None if no match.
        """
        if fact.category == "relationship":
            search_terms = [
                t for t in (fact.subordinate, fact.manager) if t
            ]
        else:
            search_terms = [fact.value]

        for term in search_terms:
            term_lower = term.lower()
            for line in lines:
                if term_lower in line.text.lower():
                    return f"{line.canonical_key}: {line.text}"

        return None

    @staticmethod
    def _match_raw_source_line(
        fact: LLMInferredFact, raw_lines: list[str]
    ) -> str | None:
        """Find the originating raw text line for a fact (best-effort).

        Same matching algorithm as ``_match_source_line`` (substring match,
        case-insensitive, first match wins) but returns the raw line as-is —
        no ``canonical_key:`` prefix — per §9.5.
        """
        if fact.category == "relationship":
            search_terms = [
                t for t in (fact.subordinate, fact.manager) if t
            ]
        else:
            search_terms = [fact.value]

        for term in search_terms:
            term_lower = term.lower()
            for raw_line in raw_lines:
                if term_lower in raw_line.lower():
                    return raw_line

        return None

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
            # Compute source_excerpt per §10.4:
            # 1. Use source_line if available (originating tagged line).
            # 2. Fall back to "[source] " + first 200 chars of raw_content.
            if fact.source_line:
                source_excerpt = fact.source_line
            else:
                source = await self._source_repo.get_by_id(fact.source_id)
                if source is not None and source.raw_content:
                    source_excerpt = f"[source] {source.raw_content[:200]}"
                else:
                    source_excerpt = ""

            items.append({
                "fact_id": fact.id,
                "category": fact.category,
                "inferred_value": fact.inferred_value,
                "status": fact.status,
                "source_id": fact.source_id,
                "source_excerpt": source_excerpt,
                "candidates": [],  # Phase 2: always empty; Phase 3 Unit 4 adds disambiguation
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
        # All other categories (technology, process, product, cgkra-*, swot-*, other):
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
        """Delegate to PersonService.get_or_create_person_from_value().

        Preserves Phase 2 dedup+backfill behavior via the domain service.
        """
        person = await self._person_service.get_or_create_person_from_value(
            company_id, fact.inferred_value
        )
        return str(person.id)

    async def _accept_functional_area(
        self, company_id: UUID, fact: Any
    ) -> str:
        """Delegate to FunctionalAreaService.create_area_safe().

        Preserves Phase 2 dedup behavior via the domain service.
        """
        area = await self._functional_area_service.create_area_safe(
            company_id, fact.inferred_value.strip()
        )
        return str(area.id)

    async def _accept_action_item(
        self, company_id: UUID, fact: Any
    ) -> str:
        """Create an action item from the fact.

        If an open action item with the same description already exists for
        this company (case-insensitive match), reuses the existing row.

        Note: ActionItemRepository used directly — no ActionItemService yet
        (partial §9.2 compliance).
        """
        description = fact.inferred_value.strip()

        # Check for existing open action item with same description
        existing = await self._action_item_repo.get_by_description_iexact(
            company_id, description
        )
        if existing is not None:
            return str(existing.id)

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
        """Parse "subordinate > manager" from inferred_value, resolve names, create relationship.

        Delegates name resolution to PersonService.resolve_person().

        If the (subordinate, manager) pair already exists, reuses the existing
        relationship row (same dedup pattern as _accept_functional_area).

        Note: RelationshipRepository used directly — no RelationshipService
        (partial §9.2 compliance).
        """
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

        # Resolve subordinate and manager via PersonService
        sub_id = await self._person_service.resolve_person(company_id, sub_name)
        mgr_id = await self._person_service.resolve_person(company_id, mgr_name)

        # Check for existing relationship (handles UNIQUE constraint uq_relationships_sub_mgr)
        existing = await self._relationship_repo.get_by_sub_mgr(sub_id, mgr_id)
        if existing is not None:
            # Still update reports_to in case it was cleared
            await self._person_service._person_repo.update_reports_to(sub_id, mgr_id)
            return str(existing.id)

        # Create relationship row
        relationship = await self._relationship_repo.create(
            company_id=company_id,
            subordinate_person_id=sub_id,
            manager_person_id=mgr_id,
            inferred_fact_id=fact.id,
        )

        # Set reports_to_person_id on the subordinate
        await self._person_service._person_repo.update_reports_to(sub_id, mgr_id)

        return str(relationship.id)
