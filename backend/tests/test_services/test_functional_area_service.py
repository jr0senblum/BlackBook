"""Tests for FunctionalAreaService — Phase 3 Unit 1.

Tests cover:
  - create_area: creates a new area (no dedup)
  - create_area_safe: deduplicates existing name (case-insensitive)
  - create_area_no_dedup: create_area() does NOT deduplicate (IntegrityError on duplicate)
  - list_areas: returns all areas for a company
  - get_area: returns area detail with company guard
  - get_area wrong company: raises AreaCompanyMismatchError
  - get_area not found: raises AreaNotFoundError
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Company
from app.repositories.action_item_repository import ActionItemRepository
from app.repositories.functional_area_repository import FunctionalAreaRepository
from app.repositories.person_repository import PersonRepository
from app.exceptions import AreaCompanyMismatchError, AreaNameConflictError, AreaNotFoundError
from app.services.functional_area_service import FunctionalAreaService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="session")
async def area_service(db_session: AsyncSession) -> FunctionalAreaService:
    """Provide a FunctionalAreaService wired to test repos."""
    return FunctionalAreaService(
        area_repo=FunctionalAreaRepository(db_session),
        person_repo=PersonRepository(db_session),
        action_item_repo=ActionItemRepository(db_session),
    )


@pytest_asyncio.fixture(loop_scope="session")
async def area_repo(db_session: AsyncSession) -> FunctionalAreaRepository:
    return FunctionalAreaRepository(db_session)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_company(db: AsyncSession, name: str | None = None) -> Company:
    c = Company(name=name or f"AreaSvcTestCo-{uuid4().hex[:8]}")
    db.add(c)
    await db.flush()
    await db.refresh(c)
    return c


# ---------------------------------------------------------------------------
# create_area tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_create_area(
    db_session: AsyncSession, area_service: FunctionalAreaService
):
    """create_area creates a new functional area."""
    company = await _make_company(db_session)
    area_name = f"Engineering-{uuid4().hex[:6]}"

    area = await area_service.create_area(company.id, area_name)

    assert area.name == area_name
    assert area.company_id == company.id


# ---------------------------------------------------------------------------
# create_area_safe tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_create_area_safe_deduplicates(
    db_session: AsyncSession, area_service: FunctionalAreaService, area_repo
):
    """create_area_safe with existing name (case-insensitive) returns existing row."""
    company = await _make_company(db_session)
    area_name = f"Platform-{uuid4().hex[:6]}"

    existing = await area_repo.create(company_id=company.id, name=area_name)

    # Same name, different case
    area = await area_service.create_area_safe(company.id, area_name.upper())
    assert area.id == existing.id


# ---------------------------------------------------------------------------
# create_area no-dedup test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_create_area_no_dedup(
    db_session: AsyncSession, area_service: FunctionalAreaService, area_repo
):
    """create_area() does NOT deduplicate — raises AreaNameConflictError on exact duplicate.

    This verifies that create_area (used by correct_fact) always attempts
    to create a new row. If the name collides with an existing area, the
    UNIQUE constraint on (company_id, name) is caught and converted to
    AreaNameConflictError (409).
    """
    company = await _make_company(db_session)
    area_name = f"DataScience-{uuid4().hex[:6]}"

    await area_repo.create(company_id=company.id, name=area_name)

    with pytest.raises(AreaNameConflictError):
        await area_service.create_area(company.id, area_name)


# ---------------------------------------------------------------------------
# list_areas tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_list_areas(
    db_session: AsyncSession, area_service: FunctionalAreaService, area_repo
):
    """list_areas returns all areas for a company, ordered by name."""
    company = await _make_company(db_session)

    await area_repo.create(company_id=company.id, name=f"Bravo-{uuid4().hex[:6]}")
    await area_repo.create(company_id=company.id, name=f"Alpha-{uuid4().hex[:6]}")

    areas = await area_service.list_areas(company.id)
    assert len(areas) == 2
    # Ordered by name ascending
    assert areas[0].name < areas[1].name


@pytest.mark.asyncio(loop_scope="session")
async def test_list_areas_empty(
    db_session: AsyncSession, area_service: FunctionalAreaService
):
    """list_areas with no areas returns empty list."""
    company = await _make_company(db_session)

    areas = await area_service.list_areas(company.id)
    assert areas == []


# ---------------------------------------------------------------------------
# get_area tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="session")
async def test_get_area(
    db_session: AsyncSession, area_service: FunctionalAreaService, area_repo
):
    """get_area returns area detail dict."""
    company = await _make_company(db_session)
    area = await area_repo.create(company_id=company.id, name=f"GetArea-{uuid4().hex[:6]}")

    detail = await area_service.get_area(company.id, area.id)

    assert detail["area_id"] == area.id
    assert detail["name"] == area.name
    assert "notes" in detail
    assert "created_at" in detail


@pytest.mark.asyncio(loop_scope="session")
async def test_get_area_not_found(
    db_session: AsyncSession, area_service: FunctionalAreaService
):
    """get_area with nonexistent ID raises AreaNotFoundError."""
    company = await _make_company(db_session)

    with pytest.raises(AreaNotFoundError):
        await area_service.get_area(company.id, uuid4())


@pytest.mark.asyncio(loop_scope="session")
async def test_get_area_wrong_company(
    db_session: AsyncSession, area_service: FunctionalAreaService, area_repo
):
    """get_area with area belonging to different company raises AreaCompanyMismatchError."""
    company = await _make_company(db_session)
    other_company = await _make_company(db_session)
    area = await area_repo.create(company_id=company.id, name=f"WrongCo-{uuid4().hex[:6]}")

    with pytest.raises(AreaCompanyMismatchError):
        await area_service.get_area(other_company.id, area.id)
