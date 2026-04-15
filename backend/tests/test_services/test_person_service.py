"""Tests for PersonService — Phase 3 Unit 1.

Tests cover:
  - create_person: creates a person with name and title; with FK fields
  - create_person_from_value: parses "name, title" (with and without comma)
  - get_or_create_person_from_value: dedup, backfill, create-if-new,
    title preservation when existing person already has title
  - resolve_person: exact match, multiple matches (fuzzy tiebreak), no match (stub creation)
  - list_people: returns all persons for a company
  - get_person: returns basic detail; company guard; not-found guard
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import PersonCompanyMismatchError, PersonNotFoundError
from app.models.base import Company, FunctionalArea
from app.repositories.action_item_repository import ActionItemRepository
from app.repositories.functional_area_repository import FunctionalAreaRepository
from app.repositories.inferred_fact_repository import InferredFactRepository
from app.repositories.person_repository import PersonRepository
from app.services.person_service import PersonService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="session")
async def person_service(db_session: AsyncSession) -> PersonService:
    """Provide a PersonService wired to test repos."""
    return PersonService(
        person_repo=PersonRepository(db_session),
        functional_area_repo=FunctionalAreaRepository(db_session),
        action_item_repo=ActionItemRepository(db_session),
        inferred_fact_repo=InferredFactRepository(db_session),
    )


@pytest_asyncio.fixture(loop_scope="session")
async def person_repo(db_session: AsyncSession) -> PersonRepository:
    return PersonRepository(db_session)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_company(db: AsyncSession, name: str | None = None) -> Company:
    c = Company(name=name or f"PersonSvcTestCo-{uuid4().hex[:8]}")
    db.add(c)
    await db.flush()
    await db.refresh(c)
    return c


# ---------------------------------------------------------------------------
# create_person tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_create_person(
    db_session: AsyncSession, person_service: PersonService
):
    """create_person creates a person with name and title."""
    company = await _make_company(db_session)

    person = await person_service.create_person(
        company.id, name="Alice Smith", title="VP Engineering"
    )

    assert person.name == "Alice Smith"
    assert person.title == "VP Engineering"
    assert person.company_id == company.id


# ---------------------------------------------------------------------------
# create_person_from_value tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_create_person_from_value_with_comma(
    db_session: AsyncSession, person_service: PersonService
):
    """create_person_from_value with comma parses name and title."""
    company = await _make_company(db_session)

    person = await person_service.create_person_from_value(
        company.id, "Jane Smith, VP"
    )

    assert person.name == "Jane Smith"
    assert person.title == "VP"
    assert person.company_id == company.id


@pytest.mark.asyncio(loop_scope="session")
async def test_create_person_from_value_without_comma(
    db_session: AsyncSession, person_service: PersonService
):
    """create_person_from_value without comma uses full value as name."""
    company = await _make_company(db_session)

    person = await person_service.create_person_from_value(
        company.id, "Jane Smith"
    )

    assert person.name == "Jane Smith"
    assert person.title is None


# ---------------------------------------------------------------------------
# get_or_create_person_from_value tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_get_or_create_person_dedup_existing(
    db_session: AsyncSession, person_service: PersonService, person_repo
):
    """get_or_create with existing name (case-insensitive) reuses existing row."""
    company = await _make_company(db_session)

    existing = await person_repo.create(
        company_id=company.id, name="Bob Jones", title="Director"
    )

    person = await person_service.get_or_create_person_from_value(
        company.id, "bob jones, CTO"
    )

    assert person.id == existing.id
    # Title should NOT be overwritten — existing already has one
    assert person.title == "Director"


@pytest.mark.asyncio(loop_scope="session")
async def test_get_or_create_person_backfill_title(
    db_session: AsyncSession, person_service: PersonService, person_repo
):
    """get_or_create backfills title when existing person has none."""
    company = await _make_company(db_session)

    existing = await person_repo.create(
        company_id=company.id, name="Carol White"
    )
    assert existing.title is None

    person = await person_service.get_or_create_person_from_value(
        company.id, "Carol White, VP Sales"
    )

    assert person.id == existing.id
    # Verify title was back-filled by re-fetching
    refreshed = await person_repo.get_by_id(existing.id)
    assert refreshed.title == "VP Sales"


@pytest.mark.asyncio(loop_scope="session")
async def test_get_or_create_person_multiple_matches_reuses_first(
    db_session: AsyncSession, person_service: PersonService, person_repo
):
    """get_or_create with multiple name matches reuses one of the existing rows.

    The spec (§10.4) says "if a match exists, reuse it" using singular language.
    When multiple persons share the same name (case-insensitively), the method
    returns the first match from the query. No new person is created.
    """
    company = await _make_company(db_session)
    dup_name = f"MultiMatch-{uuid4().hex[:6]}"

    p1 = await person_repo.create(
        company_id=company.id, name=dup_name, title="VP"
    )
    p2 = await person_repo.create(
        company_id=company.id, name=dup_name, title="Director"
    )

    person = await person_service.get_or_create_person_from_value(
        company.id, f"{dup_name}, New Title"
    )

    # Must reuse an existing row, NOT create a third
    assert person.id in {p1.id, p2.id}
    # Verify no new person was created
    all_matches = await person_repo.get_by_name_iexact(company.id, dup_name)
    assert len(all_matches) == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_get_or_create_person_no_match_creates(
    db_session: AsyncSession, person_service: PersonService, person_repo
):
    """get_or_create with no name match creates a new person."""
    company = await _make_company(db_session)
    unique_name = f"NewPerson-{uuid4().hex[:6]}"

    person = await person_service.get_or_create_person_from_value(
        company.id, f"{unique_name}, Engineer"
    )

    assert person.name == unique_name
    assert person.title == "Engineer"
    assert person.company_id == company.id

    # Verify it actually exists in the database
    fetched = await person_repo.get_by_id(person.id)
    assert fetched is not None
    assert fetched.name == unique_name


# ---------------------------------------------------------------------------
# resolve_person tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_resolve_person_exact_match(
    db_session: AsyncSession, person_service: PersonService, person_repo
):
    """resolve_person with one exact match returns existing ID."""
    company = await _make_company(db_session)
    unique_name = f"ResolveExact-{uuid4().hex[:6]}"

    existing = await person_repo.create(
        company_id=company.id, name=unique_name, title="CTO"
    )

    resolved_id = await person_service.resolve_person(company.id, unique_name)
    assert resolved_id == existing.id


@pytest.mark.asyncio(loop_scope="session")
async def test_resolve_person_multiple_matches_uses_highest_fuzzy_score(
    db_session: AsyncSession, person_service: PersonService, person_repo
):
    """resolve_person with multiple matches uses the highest fuzzy-score match per §10.4."""
    company = await _make_company(db_session)
    dup_name = f"ResolveDup-{uuid4().hex[:6]}"

    p1 = await person_repo.create(
        company_id=company.id, name=dup_name, title="VP"
    )
    p2 = await person_repo.create(
        company_id=company.id, name=dup_name, title="Director"
    )

    resolved_id = await person_service.resolve_person(company.id, dup_name)
    # Both share the same name; fuzzy scoring uses "name, title" when title
    # is present. Either is acceptable since the names are identical — the
    # key requirement is that resolve_person doesn't crash and returns a
    # valid existing ID (not a new stub).
    assert resolved_id in {p1.id, p2.id}


@pytest.mark.asyncio(loop_scope="session")
async def test_resolve_person_no_match_creates_stub(
    db_session: AsyncSession, person_service: PersonService, person_repo
):
    """resolve_person with no match creates a stub person."""
    company = await _make_company(db_session)
    stub_name = f"StubPerson-{uuid4().hex[:6]}"

    resolved_id = await person_service.resolve_person(company.id, stub_name)

    # Verify stub was created
    stub = await person_repo.get_by_id(resolved_id)
    assert stub is not None
    assert stub.name == stub_name
    assert stub.title is None  # stub has no title
    assert stub.company_id == company.id


# ---------------------------------------------------------------------------
# create_person with FK fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_create_person_with_fk_fields(
    db_session: AsyncSession, person_service: PersonService, person_repo
):
    """create_person with primary_area_id and reports_to_person_id persists FK fields."""
    company = await _make_company(db_session)

    # Create area and manager first
    area = FunctionalArea(company_id=company.id, name=f"Area-{uuid4().hex[:6]}")
    db_session.add(area)
    await db_session.flush()
    await db_session.refresh(area)

    manager = await person_repo.create(
        company_id=company.id, name=f"Manager-{uuid4().hex[:6]}"
    )

    person = await person_service.create_person(
        company.id,
        name="FK Person",
        title="Engineer",
        primary_area_id=area.id,
        reports_to_person_id=manager.id,
    )

    assert person.primary_area_id == area.id
    assert person.reports_to_person_id == manager.id


# ---------------------------------------------------------------------------
# get_or_create title preservation test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_get_or_create_person_does_not_overwrite_existing_title(
    db_session: AsyncSession, person_service: PersonService, person_repo
):
    """get_or_create with existing person who already has a title does NOT overwrite it."""
    company = await _make_company(db_session)

    existing = await person_repo.create(
        company_id=company.id, name="TitleKeep Person", title="Original Title"
    )

    person = await person_service.get_or_create_person_from_value(
        company.id, "TitleKeep Person, New Title"
    )

    assert person.id == existing.id
    # Title must be preserved — NOT overwritten
    refreshed = await person_repo.get_by_id(existing.id)
    assert refreshed.title == "Original Title"


# ---------------------------------------------------------------------------
# list_people tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_list_people(
    db_session: AsyncSession, person_service: PersonService, person_repo
):
    """list_people returns all persons for a company, ordered by name."""
    company = await _make_company(db_session)

    await person_repo.create(company_id=company.id, name=f"Bravo-{uuid4().hex[:6]}")
    await person_repo.create(company_id=company.id, name=f"Alpha-{uuid4().hex[:6]}")

    people = await person_service.list_people(company.id)
    assert len(people) == 2
    # Ordered by name ascending
    assert people[0].name < people[1].name


@pytest.mark.asyncio(loop_scope="session")
async def test_list_people_empty(
    db_session: AsyncSession, person_service: PersonService
):
    """list_people with no people returns empty list."""
    company = await _make_company(db_session)

    people = await person_service.list_people(company.id)
    assert people == []


# ---------------------------------------------------------------------------
# get_person tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_get_person(
    db_session: AsyncSession, person_service: PersonService, person_repo
):
    """get_person returns basic detail dict."""
    company = await _make_company(db_session)
    person = await person_repo.create(
        company_id=company.id, name="Detail Person", title="VP"
    )

    detail = await person_service.get_person(company.id, person.id)

    assert detail["person_id"] == person.id
    assert detail["name"] == "Detail Person"
    assert detail["title"] == "VP"
    assert "primary_area_id" in detail
    assert "reports_to_person_id" in detail


@pytest.mark.asyncio(loop_scope="session")
async def test_get_person_not_found(
    db_session: AsyncSession, person_service: PersonService
):
    """get_person with nonexistent ID raises PersonNotFoundError."""
    company = await _make_company(db_session)

    with pytest.raises(PersonNotFoundError):
        await person_service.get_person(company.id, uuid4())


@pytest.mark.asyncio(loop_scope="session")
async def test_get_person_wrong_company(
    db_session: AsyncSession, person_service: PersonService, person_repo
):
    """get_person with person belonging to different company raises PersonCompanyMismatchError."""
    company = await _make_company(db_session)
    other_company = await _make_company(db_session)
    person = await person_repo.create(
        company_id=company.id, name="WrongCo Person"
    )

    with pytest.raises(PersonCompanyMismatchError):
        await person_service.get_person(other_company.id, person.id)
