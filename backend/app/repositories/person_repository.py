"""PersonRepository — database access for the persons table."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Person


class PersonRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        *,
        company_id: UUID,
        name: str,
        title: str | None = None,
        primary_area_id: UUID | None = None,
        reports_to_person_id: UUID | None = None,
    ) -> Person:
        """Insert a new person row."""
        person = Person(
            company_id=company_id,
            name=name,
            title=title,
            primary_area_id=primary_area_id,
            reports_to_person_id=reports_to_person_id,
        )
        self._db.add(person)
        await self._db.flush()
        await self._db.refresh(person)
        return person

    async def get_by_id(self, person_id: UUID) -> Person | None:
        """Return a person by primary key, or None."""
        result = await self._db.execute(
            select(Person).where(Person.id == person_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name_iexact(
        self, company_id: UUID, name: str
    ) -> list[Person]:
        """Return persons matching (company_id, name) case-insensitively.

        May return 0, 1, or multiple matches (persons table has no
        unique constraint on name).
        """
        result = await self._db.execute(
            select(Person).where(
                Person.company_id == company_id,
                func.lower(Person.name) == name.lower(),
            )
        )
        return list(result.scalars().all())

    async def list_by_company(self, company_id: UUID) -> list[Person]:
        """Return all persons for a company, ordered by name."""
        result = await self._db.execute(
            select(Person)
            .where(Person.company_id == company_id)
            .order_by(Person.name.asc())
        )
        return list(result.scalars().all())

    async def update_title(
        self, person_id: UUID, title: str
    ) -> Person:
        """Update the title for a person.

        Raises ValueError if the person_id does not exist.
        """
        person = await self.get_by_id(person_id)
        if person is None:
            raise ValueError(f"Person not found: {person_id}")
        person.title = title
        await self._db.flush()
        await self._db.refresh(person)
        return person

    async def update_reports_to(
        self, person_id: UUID, manager_person_id: UUID | None
    ) -> Person:
        """Update the reports_to_person_id for a person.

        Raises ValueError if the person_id does not exist.
        """
        person = await self.get_by_id(person_id)
        if person is None:
            raise ValueError(f"Person not found: {person_id}")
        person.reports_to_person_id = manager_person_id
        await self._db.flush()
        await self._db.refresh(person)
        return person
