"""Pydantic request/response schemas for sources."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SourceUploadResponse(BaseModel):
    """POST /sources/upload response."""

    source_id: str
    status: str


class SourceListItem(BaseModel):
    """Single item in the source list."""

    source_id: UUID
    type: str
    subject_or_filename: str | None
    received_at: datetime
    status: str
    error: str | None


class SourceListResponse(BaseModel):
    """GET /companies/{id}/sources paginated response."""

    total: int
    limit: int
    offset: int
    items: list[SourceListItem]


class SourceDetail(BaseModel):
    """GET /sources/{id} full source detail."""

    source_id: UUID
    company_id: UUID
    type: str
    subject_or_filename: str | None
    raw_content: str
    received_at: datetime
    who: str | None
    interaction_date: str | None
    src: str | None
    status: str
    error: str | None


class SourceStatusResponse(BaseModel):
    """GET /sources/{id}/status lightweight poll response."""

    source_id: str
    status: str
