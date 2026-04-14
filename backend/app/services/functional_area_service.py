"""FunctionalAreaService — domain service owning functional area lifecycle.

Responsibilities:
  - create_area: insert a new area (no dedup — for correct)
  - create_area_safe: dedup variant (for accept)
  - list_areas: delegate to repo
  - get_area: enriched detail (stub until Unit 7)
  - update_area / delete_area: stubs until Unit 7 repo methods exist
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.exceptions import AreaNameConflictError, AreaNotFoundError
from app.models.base import FunctionalArea
from app.repositories.action_item_repository import ActionItemRepository
from app.repositories.functional_area_repository import FunctionalAreaRepository
from app.repositories.person_repository import PersonRepository

logger = logging.getLogger(__name__)


class FunctionalAreaService:
    def __init__(
        self,
        *,
        area_repo: FunctionalAreaRepository,
        person_repo: PersonRepository,
        action_item_repo: ActionItemRepository,
    ):
        self._area_repo = area_repo
        self._person_repo = person_repo
        self._action_item_repo = action_item_repo

    # ── Create ──────────────────────────────────────────────────

    async def create_area(
        self,
        company_id: UUID,
        name: str,
        *,
        notes: str | None = None,
    ) -> FunctionalArea:
        """Insert a new functional area row.

        Does NOT deduplicate — the UNIQUE constraint on (company_id, name)
        will raise IntegrityError on a true duplicate. This is correct per
        spec: the investigator's tool for linking to an existing area is
        merge, not correct.
        """
        return await self._area_repo.create(
            company_id=company_id, name=name
        )

    async def create_area_safe(
        self, company_id: UUID, name: str
    ) -> FunctionalArea:
        """Deduplicating create — used only by accept_fact.

        If an area with the same name already exists (case-insensitive),
        returns the existing row. Otherwise creates a new one. Preserves
        Phase 2 behavior to prevent UNIQUE constraint violations on accept.
        """
        existing = await self._area_repo.get_by_name_iexact(company_id, name)
        if existing is not None:
            return existing
        return await self._area_repo.create(
            company_id=company_id, name=name
        )

    # ── List / Get ──────────────────────────────────────────────

    async def list_areas(
        self, company_id: UUID
    ) -> list[FunctionalArea]:
        """Return all functional areas for a company, ordered by name."""
        return await self._area_repo.list_by_company(company_id)

    async def get_area(
        self, company_id: UUID, area_id: UUID
    ) -> dict:
        """Return enriched area detail.

        Enriched with people, action items, notes. Full implementation
        in Unit 7.
        """
        area = await self._area_repo.get_by_id(area_id)
        if area is None:
            raise AreaNotFoundError(f"Functional area not found: {area_id}")
        if area.company_id != company_id:
            raise AreaNotFoundError(
                f"Functional area {area_id} does not belong to company {company_id}"
            )
        # Basic detail — enrichment added in Unit 7
        return {
            "area_id": area.id,
            "name": area.name,
            "notes": area.notes,
            "created_at": area.created_at,
        }

    # ── Update / Delete (stubs until Unit 7) ────────────────────

    async def update_area(
        self,
        company_id: UUID,
        area_id: UUID,
        *,
        name: str | None = None,
        notes: str | None = None,
    ) -> FunctionalArea:
        """Update specified fields on a functional area.

        Note: depends on FunctionalAreaRepository.update() added in Unit 7.
        """
        raise NotImplementedError(
            "FunctionalAreaService.update_area() requires "
            "FunctionalAreaRepository.update() which is added in Unit 7"
        )

    async def delete_area(
        self, company_id: UUID, area_id: UUID
    ) -> None:
        """Delete a functional area.

        Note: depends on FunctionalAreaRepository.delete() added in Unit 7.
        """
        raise NotImplementedError(
            "FunctionalAreaService.delete_area() requires "
            "FunctionalAreaRepository.delete() which is added in Unit 7"
        )
