"""Pydantic schemas for inferred facts — LLM output model and review endpoints."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator, model_validator

# Valid categories from §6.3 / §11.5 CHECK constraint.
VALID_CATEGORIES = frozenset({
    "functional-area",
    "person",
    "relationship",
    "technology",
    "process",
    "product",
    "cgkra-cs",
    "cgkra-gw",
    "cgkra-kp",
    "cgkra-rm",
    "cgkra-aop",
    "swot-s",
    "swot-w",
    "swot-o",
    "swot-th",
    "action-item",
    "other",
})


class LLMInferredFact(BaseModel):
    """A single fact extracted by the LLM.

    Used as the validated output contract between InferenceService and
    IngestionService.
    """

    category: str
    value: str
    subordinate: str | None = None
    manager: str | None = None

    @field_validator("category")
    @classmethod
    def _category_valid(cls, v: str) -> str:
        if v not in VALID_CATEGORIES:
            raise ValueError(f"unknown category: {v}")
        return v

    @field_validator("value")
    @classmethod
    def _value_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("value must be non-empty")
        return v

    @model_validator(mode="after")
    def _relationship_fields(self) -> "LLMInferredFact":
        if self.category == "relationship":
            if not self.subordinate or not self.subordinate.strip():
                raise ValueError(
                    "relationship facts require non-empty subordinate"
                )
            if not self.manager or not self.manager.strip():
                raise ValueError(
                    "relationship facts require non-empty manager"
                )
        return self


class PendingFactItem(BaseModel):
    """Single item in the pending review list."""

    fact_id: UUID
    category: str
    inferred_value: str
    status: str
    source_id: UUID
    source_excerpt: str
    candidates: list = []


class PendingFactListResponse(BaseModel):
    """GET /companies/{id}/pending paginated response."""

    total: int
    limit: int
    offset: int
    items: list[PendingFactItem]


class AcceptResponse(BaseModel):
    """POST .../accept response."""

    fact_id: UUID
    status: str
    entity_id: str | None


class DismissResponse(BaseModel):
    """POST .../dismiss response."""

    fact_id: UUID
    status: str


# ---------------------------------------------------------------------------
# Merge / Correct / Update fact value schemas (Unit 3)
# ---------------------------------------------------------------------------


class MergeRequest(BaseModel):
    """POST .../merge request body."""

    target_entity_id: UUID


class MergeResponse(BaseModel):
    """POST .../merge response."""

    fact_id: UUID
    status: Literal["merged"]


class CorrectRequest(BaseModel):
    """POST .../correct request body."""

    corrected_value: str

    @field_validator("corrected_value")
    @classmethod
    def _corrected_value_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("corrected_value must be non-empty")
        return v


class CorrectResponse(BaseModel):
    """POST .../correct response."""

    fact_id: UUID
    status: Literal["corrected"]
    entity_id: str | None


class UpdateFactValueRequest(BaseModel):
    """PUT /companies/{id}/facts/{fact_id} request body."""

    corrected_value: str

    @field_validator("corrected_value")
    @classmethod
    def _corrected_value_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("corrected_value must be non-empty")
        return v


class UpdateFactValueResponse(BaseModel):
    """PUT /companies/{id}/facts/{fact_id} response."""

    fact_id: UUID
    status: str
    corrected_value: str
