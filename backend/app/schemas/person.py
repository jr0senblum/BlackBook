"""Pydantic schemas for people endpoints (§10.5)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator


class PersonCreateInput(BaseModel):
    """POST /companies/{id}/people request body."""

    name: str
    title: str | None = None
    primary_area_id: UUID | None = None
    reports_to_person_id: UUID | None = None

    @field_validator("name")
    @classmethod
    def _name_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must be non-empty")
        return v


class PersonUpdateInput(BaseModel):
    """PUT /companies/{id}/people/{person_id} request body.

    All fields are optional.  Null semantics per field:
      - name: NOT NULL in DB — explicitly sending null is rejected.
      - title: nullable — null clears the title.
      - primary_area_id: nullable — null unlinks person from their area.
      - reports_to_person_id: nullable — null removes the reporting relationship.

    Only fields present in the request body (model_fields_set) are updated;
    omitted fields are left unchanged.
    """

    name: str | None = None
    title: str | None = None
    primary_area_id: UUID | None = None
    reports_to_person_id: UUID | None = None

    @model_validator(mode="after")
    def _reject_null_name(self) -> "PersonUpdateInput":
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        return self

    @field_validator("name")
    @classmethod
    def _name_non_empty(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name must be non-empty")
        return v


class ActionItemSummary(BaseModel):
    """Summary of an action item embedded in PersonDetail."""

    item_id: UUID
    description: str
    status: str
    notes: str | None
    created_at: datetime


class LinkedFactSummary(BaseModel):
    """Summary of a linked inferred fact embedded in PersonDetail.

    ``value`` is the effective investigator-approved value:
    corrected_value if set, otherwise inferred_value.
    """

    fact_id: UUID
    category: str
    value: str
    source_id: UUID


class PersonDetail(BaseModel):
    """GET /companies/{id}/people/{person_id} response."""

    person_id: UUID
    name: str
    title: str | None
    primary_area_id: UUID | None
    primary_area_name: str | None
    reports_to_person_id: UUID | None
    reports_to_name: str | None
    action_items: list[ActionItemSummary]
    inferred_facts: list[LinkedFactSummary]


class PersonListItem(BaseModel):
    """Single item in the people list response."""

    person_id: UUID
    name: str
    title: str | None
    primary_area_id: UUID | None
    primary_area_name: str | None


class PersonListResponse(BaseModel):
    """GET /companies/{id}/people response."""

    items: list[PersonListItem]


class PersonCreatedResponse(BaseModel):
    """POST /companies/{id}/people 201 response."""

    person_id: UUID
    name: str
