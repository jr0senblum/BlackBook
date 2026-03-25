"""CompanyRepository — database access for the companies table."""

from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Company, InferredFact


class CompanyRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(self, name: str, mission: str | None = None, vision: str | None = None) -> Company:
        """Insert a new company row."""
        company = Company(name=name, mission=mission, vision=vision)
        self._db.add(company)
        await self._db.flush()
        return company

    async def get_by_id(self, company_id: UUID) -> Company | None:
        """Return a company by primary key, or None."""
        result = await self._db.execute(select(Company).where(Company.id == company_id))
        return result.scalar_one_or_none()

    async def get_by_name_iexact(self, name: str) -> Company | None:
        """Return a company with a case-insensitive exact name match, or None."""
        result = await self._db.execute(
            select(Company).where(func.lower(Company.name) == name.lower())
        )
        return result.scalar_one_or_none()

    async def list_all(self, limit: int = 100, offset: int = 0) -> tuple[list[dict], int]:
        """Return paginated company list with pending_count, ordered by name asc.

        Returns (items, total) where each item is a dict with
        id, name, updated_at, pending_count.
        """
        # Subquery: count of pending inferred_facts per company.
        pending_sq = (
            select(
                InferredFact.company_id,
                func.count().label("pending_count"),
            )
            .where(InferredFact.status == "pending")
            .group_by(InferredFact.company_id)
            .subquery()
        )

        # Main query with LEFT JOIN to include companies with zero pending.
        stmt = (
            select(
                Company.id,
                Company.name,
                Company.updated_at,
                func.coalesce(pending_sq.c.pending_count, 0).label("pending_count"),
            )
            .outerjoin(pending_sq, Company.id == pending_sq.c.company_id)
            .order_by(Company.name.asc())
        )

        # Total count (before pagination).
        count_stmt = select(func.count()).select_from(Company)
        total_result = await self._db.execute(count_stmt)
        total = total_result.scalar_one()

        # Paginated results.
        result = await self._db.execute(stmt.limit(limit).offset(offset))
        items = [
            {
                "id": row.id,
                "name": row.name,
                "updated_at": row.updated_at,
                "pending_count": row.pending_count,
            }
            for row in result.all()
        ]
        return items, total

    async def update(self, company: Company, **kwargs: str | None) -> Company:
        """Update company fields. Only provided kwargs are changed."""
        for key, value in kwargs.items():
            if hasattr(company, key):
                setattr(company, key, value)
        await self._db.flush()
        await self._db.refresh(company)
        return company

    async def delete(self, company: Company) -> None:
        """Delete a company. CASCADE handles related data."""
        await self._db.delete(company)
        await self._db.flush()
