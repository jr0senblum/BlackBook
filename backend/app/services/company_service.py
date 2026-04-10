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
        pending_count = await self._repo.get_pending_count(company_id)
        return {
            "id": company.id,
            "name": company.name,
            "mission": company.mission,
            "vision": company.vision,
            "llm_context_mode": company.llm_context_mode,
            "created_at": company.created_at,
            "updated_at": company.updated_at,
            "pending_count": pending_count,
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
        fields: dict[str, str | None],
    ) -> dict:
        """Update company fields. 404 if not found. 409 if name conflicts.

        ``fields`` contains only the keys the caller explicitly provided.
        A value of None means "clear this field."
        """
        company = await self._repo.get_by_id(company_id)
        if company is None:
            raise CompanyNotFoundError()

        # If the name is changing, check for conflicts.
        if "name" in fields:
            new_name = fields["name"]
            if new_name is not None and new_name.lower() != company.name.lower():
                existing = await self._repo.get_by_name_iexact(new_name)
                if existing is not None:
                    raise CompanyNameConflictError()

        if fields:
            company = await self._repo.update(company, **fields)

        pending_count = await self._repo.get_pending_count(company_id)
        return {
            "id": company.id,
            "name": company.name,
            "mission": company.mission,
            "vision": company.vision,
            "llm_context_mode": company.llm_context_mode,
            "created_at": company.created_at,
            "updated_at": company.updated_at,
            "pending_count": pending_count,
        }

    async def delete_company(self, company_id: UUID) -> None:
        """Delete a company. 404 if not found."""
        company = await self._repo.get_by_id(company_id)
        if company is None:
            raise CompanyNotFoundError()
        await self._repo.delete(company)
