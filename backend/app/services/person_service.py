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

from app.exceptions import PersonCompanyMismatchError, PersonNotFoundError
from app.models.base import Person
from app.repositories.action_item_repository import ActionItemRepository
from app.repositories.functional_area_repository import FunctionalAreaRepository
from app.repositories.inferred_fact_repository import InferredFactRepository
from app.repositories.person_repository import PersonRepository
from app.services.fuzzy_match import similarity_score

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

        **Spec departure (M3)**: §10.4 accept/person says "insert a new row
        into persons" with merge as the linking mechanism. This method
        deduplicates on accept instead, reusing an existing person when the
        name matches case-insensitively. Rationale: without dedup, accepting
        the same name twice creates orphaned duplicates that the investigator
        must then manually merge. Dedup-on-accept treats an exact name match
        as a clear duplicate; merge remains available for fuzzy/ambiguous cases.
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
          2. No match — create stub person (name only, title=null).
          3. Multiple matches — use the highest fuzzy-score match.
        """
        matches = await self._person_repo.get_by_name_iexact(company_id, name)
        if not matches:
            # Case 2: no match — create stub
            person = await self._person_repo.create(
                company_id=company_id, name=name
            )
            return person.id

        if len(matches) == 1:
            # Case 1: exactly one match
            return matches[0].id

        # Case 3: multiple matches — pick the highest fuzzy-score match.
        # All matches are case-insensitive exact on name, so fuzzy scoring
        # here is against the full person representation (name + title if
        # available) to distinguish between duplicates.
        best = max(
            matches,
            key=lambda p: similarity_score(
                name,
                f"{p.name}, {p.title}" if p.title else p.name,
            ),
        )
        return best.id

    # ── List / Get ──────────────────────────────────────────────

    async def list_people(self, company_id: UUID) -> list[Person]:
        """Return all persons for a company, ordered by name."""
        return await self._person_repo.list_by_company(company_id)

    async def get_person(
        self, company_id: UUID, person_id: UUID
    ) -> dict:
        """Return enriched person detail per §10.5.

        Enriched with:
          - primary_area_name: looked up from functional_area_repo
          - reports_to_name: looked up from person_repo (self-join)
          - action_items: list of action items for this person
          - inferred_facts: accepted/corrected facts linked to this person
            (name-matched + area-tagged — see list_linked_to_person)
        """
        person = await self._person_repo.get_by_id(person_id)
        if person is None:
            raise PersonNotFoundError(f"Person not found: {person_id}")
        if person.company_id != company_id:
            raise PersonCompanyMismatchError(
                f"Person {person_id} does not belong to company {company_id}"
            )

        # Enrich: area name
        primary_area_name: str | None = None
        if person.primary_area_id is not None:
            area = await self._functional_area_repo.get_by_id(person.primary_area_id)
            if area is not None:
                primary_area_name = area.name

        # Enrich: reports-to name
        reports_to_name: str | None = None
        if person.reports_to_person_id is not None:
            mgr = await self._person_repo.get_by_id(person.reports_to_person_id)
            if mgr is not None:
                reports_to_name = mgr.name

        # Enrich: action items
        action_items = await self._action_item_repo.list_by_person(person.id)

        # Enrich: linked inferred facts (name-matched + area-tagged)
        inferred_facts = await self._inferred_fact_repo.list_linked_to_person(
            company_id=company_id,
            person_id=person.id,
            person_name=person.name,
            primary_area_id=person.primary_area_id,
        )

        return {
            "person_id": person.id,
            "name": person.name,
            "title": person.title,
            "primary_area_id": person.primary_area_id,
            "primary_area_name": primary_area_name,
            "reports_to_person_id": person.reports_to_person_id,
            "reports_to_name": reports_to_name,
            "action_items": action_items,
            "inferred_facts": inferred_facts,
        }

    # ── Targeted field updates (available now) ────────────────────

    async def update_reports_to(
        self, person_id: UUID, manager_person_id: UUID | None
    ) -> Person:
        """Update the reports_to_person_id on a person.

        Used by _accept_relationship to set the convenience denormalization
        per §10.4 accept/relationship. Available immediately (unlike the
        general update_person() which depends on Unit 5).
        """
        return await self._person_repo.update_reports_to(
            person_id, manager_person_id
        )

    # ── Update / Delete (stubs until Unit 5) ────────────────────

    async def update_person(
        self, company_id: UUID, person_id: UUID, **fields
    ) -> Person:
        """Update specified fields on a person.

        Validates that the person exists and belongs to company_id before
        delegating to the repository.  Only the fields provided are updated.
        """
        person = await self._person_repo.get_by_id(person_id)
        if person is None:
            raise PersonNotFoundError(f"Person not found: {person_id}")
        if person.company_id != company_id:
            raise PersonCompanyMismatchError(
                f"Person {person_id} does not belong to company {company_id}"
            )
        return await self._person_repo.update(person_id, **fields)

    async def delete_person(
        self, company_id: UUID, person_id: UUID
    ) -> None:
        """Delete a person after validating company ownership."""
        person = await self._person_repo.get_by_id(person_id)
        if person is None:
            raise PersonNotFoundError(f"Person not found: {person_id}")
        if person.company_id != company_id:
            raise PersonCompanyMismatchError(
                f"Person {person_id} does not belong to company {company_id}"
            )
        await self._person_repo.delete(person_id)
