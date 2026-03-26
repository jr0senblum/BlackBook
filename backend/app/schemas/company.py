"""Pydantic request/response schemas for companies."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CompanyCreate(BaseModel):
    """POST /companies request body."""

    name: str = Field(..., min_length=1, max_length=500)
    mission: str | None = None
    vision: str | None = None


class CompanyUpdate(BaseModel):
    """PUT /companies/{id} request body.

    ``name`` uses ``str | None`` so the field can be omitted from the JSON
    body (Pydantic treats omitted fields as default=None and excludes them
    from ``model_fields_set``).  However, explicitly sending
    ``{"name": null}`` is rejected by the validator below because the DB
    column is NOT NULL.  ``mission`` and ``vision`` are genuinely nullable.
    """

    name: str | None = Field(None, min_length=1, max_length=500)
    mission: str | None = None
    vision: str | None = None

    @model_validator(mode="after")
    def _reject_null_name(self) -> "CompanyUpdate":
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        return self


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
