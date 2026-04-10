"""Route handlers for /companies/* endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_company_service, get_current_session
from app.schemas.company import (
    CompanyCreate,
    CompanyCreatedResponse,
    CompanyDetailResponse,
    CompanyListResponse,
    CompanyUpdate,
)
from app.services.company_service import CompanyService

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=CompanyListResponse)
async def list_companies(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    company_service: CompanyService = Depends(get_company_service),
    _session: str = Depends(get_current_session),
) -> CompanyListResponse:
    """List all companies with pending counts (paginated)."""
    result = await company_service.list_companies(limit=limit, offset=offset)
    return CompanyListResponse(**result)


@router.post("", response_model=CompanyCreatedResponse, status_code=201)
async def create_company(
    body: CompanyCreate,
    company_service: CompanyService = Depends(get_company_service),
    _session: str = Depends(get_current_session),
) -> CompanyCreatedResponse:
    """Manually create a company."""
    result = await company_service.create_company(
        name=body.name, mission=body.mission, vision=body.vision
    )
    return CompanyCreatedResponse(**result)


@router.get("/{company_id}", response_model=CompanyDetailResponse)
async def get_company(
    company_id: UUID,
    company_service: CompanyService = Depends(get_company_service),
    _session: str = Depends(get_current_session),
) -> CompanyDetailResponse:
    """Get full company profile."""
    result = await company_service.get_company(company_id)
    return CompanyDetailResponse(**result)


@router.put("/{company_id}", response_model=CompanyDetailResponse)
async def update_company(
    company_id: UUID,
    body: CompanyUpdate,
    company_service: CompanyService = Depends(get_company_service),
    _session: str = Depends(get_current_session),
) -> CompanyDetailResponse:
    """Update top-level company fields (name, mission, vision, llm_context_mode)."""
    # Only forward the fields the client explicitly included in the JSON body.
    # This lets the service distinguish "not provided" from "set to null."
    fields = body.model_dump(include=body.model_fields_set)
    result = await company_service.update_company(
        company_id=company_id,
        fields=fields,
    )
    return CompanyDetailResponse(**result)


@router.delete("/{company_id}", status_code=204)
async def delete_company(
    company_id: UUID,
    company_service: CompanyService = Depends(get_company_service),
    _session: str = Depends(get_current_session),
) -> None:
    """Delete company and all associated data."""
    await company_service.delete_company(company_id)
