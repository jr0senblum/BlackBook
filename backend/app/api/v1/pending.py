"""Route handlers for pending review endpoints.

GET  /companies/{id}/pending                    — list pending/reviewed facts
POST /companies/{id}/pending/{fact_id}/accept   — accept a fact
POST /companies/{id}/pending/{fact_id}/merge    — merge with existing entity
POST /companies/{id}/pending/{fact_id}/correct  — accept with correction
POST /companies/{id}/pending/{fact_id}/dismiss  — dismiss a fact
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_session, get_review_service
from app.schemas.inferred_fact import (
    AcceptResponse,
    CorrectRequest,
    CorrectResponse,
    DismissResponse,
    MergeRequest,
    MergeResponse,
    PendingFactItem,
    PendingFactListResponse,
)
from app.services.review_service import ReviewService

router = APIRouter(prefix="/companies", tags=["pending"])


@router.get(
    "/{company_id}/pending", response_model=PendingFactListResponse
)
async def list_pending(
    company_id: UUID,
    status: Literal["pending", "accepted", "corrected", "merged", "dismissed"] = Query("pending"),
    category: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    review_service: ReviewService = Depends(get_review_service),
    _session: str = Depends(get_current_session),
) -> PendingFactListResponse:
    """List inferred facts for a company, filtered by status and category."""
    items, total = await review_service.list_pending(
        str(company_id),
        status=status,
        category=category,
        limit=limit,
        offset=offset,
    )
    return PendingFactListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[PendingFactItem(**item) for item in items],
    )


@router.post(
    "/{company_id}/pending/{fact_id}/accept",
    response_model=AcceptResponse,
)
async def accept_fact(
    company_id: UUID,
    fact_id: UUID,
    review_service: ReviewService = Depends(get_review_service),
    _session: str = Depends(get_current_session),
) -> AcceptResponse:
    """Accept a pending fact, creating entities as needed."""
    entity_id = await review_service.accept_fact(
        str(company_id), str(fact_id)
    )
    return AcceptResponse(
        fact_id=fact_id,
        status="accepted",
        entity_id=entity_id,
    )


@router.post(
    "/{company_id}/pending/{fact_id}/dismiss",
    response_model=DismissResponse,
)
async def dismiss_fact(
    company_id: UUID,
    fact_id: UUID,
    review_service: ReviewService = Depends(get_review_service),
    _session: str = Depends(get_current_session),
) -> DismissResponse:
    """Dismiss a pending fact."""
    await review_service.dismiss_fact(str(company_id), str(fact_id))
    return DismissResponse(fact_id=fact_id, status="dismissed")


@router.post(
    "/{company_id}/pending/{fact_id}/merge",
    response_model=MergeResponse,
)
async def merge_fact(
    company_id: UUID,
    fact_id: UUID,
    body: MergeRequest,
    review_service: ReviewService = Depends(get_review_service),
    _session: str = Depends(get_current_session),
) -> MergeResponse:
    """Merge a pending fact into an existing entity."""
    await review_service.merge_fact(
        str(company_id), str(fact_id), str(body.target_entity_id)
    )
    return MergeResponse(fact_id=fact_id, status="merged")


@router.post(
    "/{company_id}/pending/{fact_id}/correct",
    response_model=CorrectResponse,
)
async def correct_fact(
    company_id: UUID,
    fact_id: UUID,
    body: CorrectRequest,
    review_service: ReviewService = Depends(get_review_service),
    _session: str = Depends(get_current_session),
) -> CorrectResponse:
    """Correct a pending fact with an investigator-supplied value."""
    entity_id = await review_service.correct_fact(
        str(company_id), str(fact_id), body.corrected_value
    )
    return CorrectResponse(
        fact_id=fact_id,
        status="corrected",
        entity_id=entity_id,
    )
