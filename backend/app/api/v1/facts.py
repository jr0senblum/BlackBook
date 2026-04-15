"""Route handlers for accepted/corrected fact editing (UC 17).

PUT /companies/{id}/facts/{fact_id} — edit corrected_value on an accepted/corrected fact
"""

from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies import get_current_session, get_review_service
from app.schemas.inferred_fact import (
    UpdateFactValueRequest,
    UpdateFactValueResponse,
)
from app.services.review_service import ReviewService

router = APIRouter(prefix="/companies", tags=["facts"])


@router.put(
    "/{company_id}/facts/{fact_id}",
    response_model=UpdateFactValueResponse,
)
async def update_fact_value(
    company_id: UUID,
    fact_id: UUID,
    body: UpdateFactValueRequest,
    review_service: ReviewService = Depends(get_review_service),
    _session: str = Depends(get_current_session),
) -> UpdateFactValueResponse:
    """Edit the corrected value of an accepted or corrected fact (UC 17)."""
    status = await review_service.update_fact_value(
        str(company_id), str(fact_id), body.corrected_value
    )
    return UpdateFactValueResponse(
        fact_id=fact_id,
        status=status,
        corrected_value=body.corrected_value,
    )
