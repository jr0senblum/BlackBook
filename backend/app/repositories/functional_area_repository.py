"""FunctionalAreaRepository — database access for the functional_areas table."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import FunctionalArea


class FunctionalAreaRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(self, *, company_id: UUID, name: str) -> FunctionalArea:
        """Insert a new functional area row."""
        area = FunctionalArea(company_id=company_id, name=name)
        self._db.add(area)
        await self._db.flush()
        await self._db.refresh(area)
        return area

    async def get_by_id(self, area_id: UUID) -> FunctionalArea | None:
        """Return a functional area by primary key, or None."""
        result = await self._db.execute(
            select(FunctionalArea).where(FunctionalArea.id == area_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name_iexact(
        self, company_id: UUID, name: str
    ) -> FunctionalArea | None:
        """Return a functional area matching (company_id, name) case-insensitively.

        Returns the existing row or None.
        """
        result = await self._db.execute(
            select(FunctionalArea).where(
                FunctionalArea.company_id == company_id,
                func.lower(FunctionalArea.name) == name.lower(),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_company(self, company_id: UUID) -> list[FunctionalArea]:
        """Return all functional areas for a company, ordered by name."""
        result = await self._db.execute(
            select(FunctionalArea)
            .where(FunctionalArea.company_id == company_id)
            .order_by(FunctionalArea.name.asc())
        )
        return list(result.scalars().all())
