"""Tests for CompanyService."""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import CompanyNameConflictError, CompanyNotFoundError
from app.repositories.company_repository import CompanyRepository
from app.services.company_service import CompanyService


@pytest_asyncio.fixture(loop_scope="session")
async def company_service(db_session: AsyncSession) -> CompanyService:
    return CompanyService(company_repo=CompanyRepository(db_session))


# ── create_company ───────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_create_company(company_service: CompanyService) -> None:
    """Creating a company returns its id and name."""
    result = await company_service.create_company(
        name="Acme Corp", mission="Build things", vision="Lead the market"
    )
    assert result["name"] == "Acme Corp"
    assert "company_id" in result


@pytest.mark.asyncio(loop_scope="session")
async def test_create_company_duplicate_name(company_service: CompanyService) -> None:
    """Duplicate name (case-insensitive) raises CompanyNameConflictError."""
    await company_service.create_company(name="Unique Corp")
    with pytest.raises(CompanyNameConflictError):
        await company_service.create_company(name="unique corp")


@pytest.mark.asyncio(loop_scope="session")
async def test_create_company_duplicate_name_upper(company_service: CompanyService) -> None:
    """Duplicate name with different casing raises CompanyNameConflictError."""
    await company_service.create_company(name="Delta Inc")
    with pytest.raises(CompanyNameConflictError):
        await company_service.create_company(name="DELTA INC")


# ── get_company ──────────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_get_company(company_service: CompanyService) -> None:
    """Getting a company by ID returns its detail."""
    created = await company_service.create_company(
        name="GetMe Corp", mission="Test mission"
    )
    result = await company_service.get_company(created["company_id"])
    assert result["name"] == "GetMe Corp"
    assert result["mission"] == "Test mission"
    assert result["pending_count"] == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_get_company_not_found(company_service: CompanyService) -> None:
    """Getting a non-existent company raises CompanyNotFoundError."""
    with pytest.raises(CompanyNotFoundError):
        await company_service.get_company(uuid4())


# ── list_companies ───────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_list_companies(company_service: CompanyService) -> None:
    """Listing companies returns a paginated response containing created companies."""
    await company_service.create_company(name="List Corp A")
    await company_service.create_company(name="List Corp B")
    result = await company_service.list_companies(limit=100, offset=0)
    assert result["total"] >= 2
    assert result["limit"] == 100
    assert result["offset"] == 0
    names = [item["name"] for item in result["items"]]
    assert "List Corp A" in names
    assert "List Corp B" in names


@pytest.mark.asyncio(loop_scope="session")
async def test_list_companies_pagination(company_service: CompanyService) -> None:
    """Pagination returns correct subset."""
    await company_service.create_company(name="Paginate Corp")
    result = await company_service.list_companies(limit=1, offset=0)
    assert result["limit"] == 1
    assert len(result["items"]) == 1
    assert result["total"] >= 1


# ── update_company ───────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_update_company(company_service: CompanyService) -> None:
    """Updating company fields returns updated data."""
    created = await company_service.create_company(name="Update Corp")
    result = await company_service.update_company(
        company_id=created["company_id"],
        fields={"name": "Updated Corp", "mission": "New mission"},
    )
    assert result["name"] == "Updated Corp"
    assert result["mission"] == "New mission"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_company_not_found(company_service: CompanyService) -> None:
    """Updating a non-existent company raises CompanyNotFoundError."""
    with pytest.raises(CompanyNotFoundError):
        await company_service.update_company(company_id=uuid4(), fields={"name": "X"})


@pytest.mark.asyncio(loop_scope="session")
async def test_update_company_name_conflict(company_service: CompanyService) -> None:
    """Renaming to an existing name (case-insensitive) raises conflict."""
    await company_service.create_company(name="Conflict Target")
    created = await company_service.create_company(name="Conflict Source")
    with pytest.raises(CompanyNameConflictError):
        await company_service.update_company(
            company_id=created["company_id"], fields={"name": "conflict target"}
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_update_company_same_name(company_service: CompanyService) -> None:
    """Updating with the same name (no actual change) succeeds without
    triggering the conflict check."""
    created = await company_service.create_company(name="Same Name Corp")
    result = await company_service.update_company(
        company_id=created["company_id"],
        fields={"name": "Same Name Corp", "mission": "Added mission"},
    )
    assert result["name"] == "Same Name Corp"
    assert result["mission"] == "Added mission"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_company_same_name_different_case(
    company_service: CompanyService,
) -> None:
    """Updating with the same name in different casing succeeds (no conflict)."""
    created = await company_service.create_company(name="CaseTest Corp")
    result = await company_service.update_company(
        company_id=created["company_id"],
        fields={"name": "casetest corp"},
    )
    assert result["name"] == "casetest corp"


@pytest.mark.asyncio(loop_scope="session")
async def test_update_company_nullify_mission(company_service: CompanyService) -> None:
    """Setting mission to None clears it."""
    created = await company_service.create_company(
        name="Nullify Corp", mission="Old mission"
    )
    result = await company_service.update_company(
        company_id=created["company_id"], fields={"mission": None}
    )
    assert result["mission"] is None


# ── delete_company ───────────────────────────────────────────────


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_company(company_service: CompanyService) -> None:
    """Deleting a company succeeds and it is no longer findable."""
    created = await company_service.create_company(name="Delete Me Corp")
    await company_service.delete_company(created["company_id"])
    with pytest.raises(CompanyNotFoundError):
        await company_service.get_company(created["company_id"])


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_company_not_found(company_service: CompanyService) -> None:
    """Deleting a non-existent company raises CompanyNotFoundError."""
    with pytest.raises(CompanyNotFoundError):
        await company_service.delete_company(uuid4())
