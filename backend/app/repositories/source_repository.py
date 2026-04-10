"""SourceRepository — database access for the sources table."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Source


class SourceRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(
        self,
        *,
        company_id: UUID,
        type: str,
        filename_or_subject: str | None,
        raw_content: str,
        file_path: str | None = None,
        who: str | None = None,
        interaction_date: str | None = None,
        src: str | None = None,
    ) -> Source:
        """Insert a new source row."""
        source = Source(
            company_id=company_id,
            type=type,
            filename_or_subject=filename_or_subject,
            raw_content=raw_content,
            file_path=file_path,
            who=who,
            interaction_date=interaction_date,
            src=src,
        )
        self._db.add(source)
        await self._db.flush()
        await self._db.refresh(source)
        return source

    async def get_by_id(self, source_id: UUID) -> Source | None:
        """Return a source by primary key, or None."""
        result = await self._db.execute(
            select(Source).where(Source.id == source_id)
        )
        return result.scalar_one_or_none()

    async def list_by_company(
        self,
        company_id: UUID,
        *,
        status: str = "all",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Source], int]:
        """Return paginated source list for a company.

        Ordered by received_at DESC.  ``status`` filters by source status;
        "all" returns all statuses.  Returns (items, total).
        """
        base = select(Source).where(Source.company_id == company_id)
        count_base = select(func.count()).select_from(Source).where(
            Source.company_id == company_id
        )

        if status != "all":
            base = base.where(Source.status == status)
            count_base = count_base.where(Source.status == status)

        total_result = await self._db.execute(count_base)
        total = total_result.scalar_one()

        result = await self._db.execute(
            base.order_by(Source.received_at.desc()).limit(limit).offset(offset)
        )
        items = list(result.scalars().all())

        return items, total

    async def list_processed_content(
        self,
        company_id: UUID,
        *,
        limit: int = 20,
    ) -> list[tuple[str, str | None]]:
        """Return (filename_or_subject, raw_content) for processed sources.

        Ordered by received_at DESC.  Used by context assembly in ``full`` mode.
        The ``limit`` caps the query to prevent loading unbounded content.
        """
        result = await self._db.execute(
            select(Source.filename_or_subject, Source.raw_content)
            .where(
                Source.company_id == company_id,
                Source.status == "processed",
            )
            .order_by(Source.received_at.desc())
            .limit(limit)
        )
        return [(row[0], row[1]) for row in result.all()]

    async def update_status(
        self,
        source_id: UUID,
        *,
        status: str,
        error: str | None = None,
        raw_llm_response: str | None = None,
    ) -> Source:
        """Update the status (and optionally error/raw_llm_response) of a source.

        Raises ValueError if the source_id does not exist.
        """
        source = await self.get_by_id(source_id)
        if source is None:
            raise ValueError(f"Source not found: {source_id}")
        source.status = status
        source.error = error
        source.raw_llm_response = raw_llm_response
        await self._db.flush()
        await self._db.refresh(source)
        return source

    async def update_file_path(self, source_id: UUID, file_path: str) -> None:
        """Set the file_path on an existing source record.

        Raises ValueError if the source_id does not exist.
        """
        source = await self.get_by_id(source_id)
        if source is None:
            raise ValueError(f"Source not found: {source_id}")
        source.file_path = file_path
        await self._db.flush()
