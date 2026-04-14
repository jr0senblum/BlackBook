"""PersonService — domain service owning person entity lifecycle.

Responsibilities:
  - create_person: insert a new person row
  - create_person_from_value: parse "name, title" and create (no dedup — for correct)
  - get_or_create_person_from_value: parse + dedup (for accept)
  - resolve_person: name resolution algorithm from §10.4
  - list_people: delegate to repo
  - get_person: enriched detail (stub until Unit 5)
  - update_person / delete_person: stubs until Unit 5 repo methods exist
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.exceptions import PersonNotFoundError
from app.models.base import Person
from app.repositories.action_item_repository import ActionItemRepository
from app.repositories.functional_area_repository import FunctionalAreaRepository
from app.repositories.inferred_fact_repository import InferredFactRepository
from app.repositories.person_repository import PersonRepository

logger = logging.getLogger(__name__)


class PersonService:
    def __init__(
        self,
        *,
        person_repo: PersonRepository,
        functional_area_repo: FunctionalAreaRepository,
        action_item_repo: ActionItemRepository,
        inferred_fact_repo: InferredFactRepository,
    ):
        self._person_repo = person_repo
        self._functional_area_repo = functional_area_repo
        self._action_item_repo = action_item_repo
        self._inferred_fact_repo = inferred_fact_repo

    # ── Value parsing helper ────────────────────────────────────

    @staticmethod
    def _parse_name_title(value: str) -> tuple[str, str | None]:
        """Parse 'name, title' from a value string.

        Split on first comma: left = name, right = title.
        If no comma, full value is name, title is None.
        """
        if "," in value:
            name, title = value.split(",", 1)
            return name.strip(), title.strip()
        return value.strip(), None

    # ── Create ──────────────────────────────────────────────────

    async def create_person(
        self,
        company_id: UUID,
        *,
        name: str,
        title: str | None = None,
        primary_area_id: UUID | None = None,
        reports_to_person_id: UUID | None = None,
    ) -> Person:
        """Insert a new person row."""
        return await self._person_repo.create(
            company_id=company_id,
            name=name,
            title=title,
            primary_area_id=primary_area_id,
            reports_to_person_id=reports_to_person_id,
        )

    async def create_person_from_value(
        self, company_id: UUID, value: str
    ) -> Person:
        """Parse value as 'name, title' and create a new person.

        Always creates — no deduplication. Used by correct_fact where the
        investigator explicitly chose correct over merge.
        """
        name, title = self._parse_name_title(value)
        return await self.create_person(
            company_id, name=name, title=title
        )

    async def get_or_create_person_from_value(
        self, company_id: UUID, value: str
    ) -> Person:
        """Parse value, dedup against existing persons, create if new.

        If a person with the same name already exists (case-insensitive),
        reuses the existing row and back-fills title if the existing person
        has none and the fact provides one. Used by accept_fact.
        """
        name, title = self._parse_name_title(value)

        matches = await self._person_repo.get_by_name_iexact(company_id, name)
        if matches:
            existing = matches[0]
            if title and not existing.title:
                await self._person_repo.update_title(existing.id, title)
            return existing

        return await self.create_person(
            company_id, name=name, title=title
        )

    # ── Resolve ─────────────────────────────────────────────────

    async def resolve_person(
        self, company_id: UUID, name: str
    ) -> UUID:
        """Resolve a person name to a person ID.

        Algorithm per §10.4:
          1. Case-insensitive exact match — if exactly one, use it.
          2. Multiple matches — use first.
          3. No match — create stub person (name only, title=null).
        """
        matches = await self._person_repo.get_by_name_iexact(company_id, name)
        if matches:
            return matches[0].id

        person = await self._person_repo.create(
            company_id=company_id, name=name
        )
        return person.id

    # ── List / Get ──────────────────────────────────────────────

    async def list_people(self, company_id: UUID) -> list[Person]:
        """Return all persons for a company, ordered by name."""
        return await self._person_repo.list_by_company(company_id)

    async def get_person(
        self, company_id: UUID, person_id: UUID
    ) -> dict:
        """Return enriched person detail.

        Enriched with area name, reports_to name, action items, linked
        inferred facts. Full implementation in Unit 5.
        """
        person = await self._person_repo.get_by_id(person_id)
        if person is None:
            raise PersonNotFoundError(f"Person not found: {person_id}")
        if person.company_id != company_id:
            from app.exceptions import PersonCompanyMismatchError

            raise PersonCompanyMismatchError(
                f"Person {person_id} does not belong to company {company_id}"
            )
        # Basic detail — enrichment added in Unit 5
        return {
            "person_id": person.id,
            "name": person.name,
            "title": person.title,
            "primary_area_id": person.primary_area_id,
            "reports_to_person_id": person.reports_to_person_id,
        }

    # ── Update / Delete (stubs until Unit 5) ────────────────────

    async def update_person(
        self, company_id: UUID, person_id: UUID, **fields
    ) -> Person:
        """Update specified fields on a person.

        Note: depends on PersonRepository.update() added in Unit 5.
        """
        raise NotImplementedError(
            "PersonService.update_person() requires PersonRepository.update() "
            "which is added in Unit 5"
        )

    async def delete_person(
        self, company_id: UUID, person_id: UUID
    ) -> None:
        """Delete a person.

        Note: depends on PersonRepository.delete() added in Unit 5.
        """
        raise NotImplementedError(
            "PersonService.delete_person() requires PersonRepository.delete() "
            "which is added in Unit 5"
        )
