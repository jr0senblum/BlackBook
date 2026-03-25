"""CompanyService — company CRUD and duplicate-name checking."""

from uuid import UUID

from app.exceptions import CompanyNameConflictError, CompanyNotFoundError
from app.repositories.company_repository import CompanyRepository


class CompanyService:
    def __init__(self, company_repo: CompanyRepository):
        self._repo = company_repo

    async def create_company(
        self, name: str, mission: str | None = None, vision: str | None = None
    ) -> dict:
        """Create a company. Blocks with 409 if exact name (case-insensitive) exists."""
        existing = await self._repo.get_by_name_iexact(name)
        if existing is not None:
            raise CompanyNameConflictError()
        company = await self._repo.create(name=name, mission=mission, vision=vision)
        return {"company_id": company.id, "name": company.name}

    async def get_company(self, company_id: UUID) -> dict:
        """Return full company detail. 404 if not found."""
        company = await self._repo.get_by_id(company_id)
        if company is None:
            raise CompanyNotFoundError()
        # For Phase 1, pending_count is always 0 (no ingestion yet).
        # In production, this would be computed via the repo.
        return {
            "id": company.id,
            "name": company.name,
            "mission": company.mission,
            "vision": company.vision,
            "created_at": company.created_at,
            "updated_at": company.updated_at,
            "pending_count": 0,
        }

    async def list_companies(self, limit: int = 100, offset: int = 0) -> dict:
        """Return paginated company list with pending counts."""
        items, total = await self._repo.list_all(limit=limit, offset=offset)
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": items,
        }

    async def update_company(
        self,
        company_id: UUID,
        name: str | None = None,
        mission: str | None = None,
        vision: str | None = None,
    ) -> dict:
        """Update company fields. 404 if not found. 409 if name conflicts."""
        company = await self._repo.get_by_id(company_id)
        if company is None:
            raise CompanyNotFoundError()

        # If the name is changing, check for conflicts.
        if name is not None and name.lower() != company.name.lower():
            existing = await self._repo.get_by_name_iexact(name)
            if existing is not None:
                raise CompanyNameConflictError()

        # Build kwargs for only the fields that were provided.
        updates: dict[str, str | None] = {}
        if name is not None:
            updates["name"] = name
        if mission is not None:
            updates["mission"] = mission
        if vision is not None:
            updates["vision"] = vision

        if updates:
            company = await self._repo.update(company, **updates)

        return {
            "id": company.id,
            "name": company.name,
            "mission": company.mission,
            "vision": company.vision,
            "created_at": company.created_at,
            "updated_at": company.updated_at,
            "pending_count": 0,
        }

    async def delete_company(self, company_id: UUID) -> None:
        """Delete a company. 404 if not found."""
        company = await self._repo.get_by_id(company_id)
        if company is None:
            raise CompanyNotFoundError()
        await self._repo.delete(company)
