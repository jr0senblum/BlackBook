"""Pydantic request/response schemas for companies."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CompanyCreate(BaseModel):
    """POST /companies request body."""

    name: str = Field(..., min_length=1, max_length=500)
    mission: str | None = None
    vision: str | None = None


class CompanyUpdate(BaseModel):
    """PUT /companies/{id} request body."""

    name: str | None = Field(None, min_length=1, max_length=500)
    mission: str | None = None
    vision: str | None = None


class CompanyCreatedResponse(BaseModel):
    """POST /companies 201 response."""

    company_id: UUID
    name: str


class CompanyListItem(BaseModel):
    """Single item in the company list."""

    id: UUID
    name: str
    updated_at: datetime
    pending_count: int


class CompanyListResponse(BaseModel):
    """GET /companies paginated response."""

    total: int
    limit: int
    offset: int
    items: list[CompanyListItem]


class CompanyDetailResponse(BaseModel):
    """GET /companies/{id} response — Phase 1 returns just the company fields."""

    id: UUID
    name: str
    mission: str | None
    vision: str | None
    created_at: datetime
    updated_at: datetime
    pending_count: int
