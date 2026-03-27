"""Route handlers for /sources/* and /companies/{id}/sources endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from app.dependencies import get_current_session, get_ingestion_service
from app.schemas.source import (
    SourceDetail,
    SourceListItem,
    SourceListResponse,
    SourceStatusResponse,
    SourceUploadResponse,
)
from app.services.ingestion_service import IngestionService
from app.workers.ingestion_worker import ingestion_queue

router = APIRouter(tags=["sources"])


@router.post("/sources/upload", response_model=SourceUploadResponse)
async def upload_source(
    file: UploadFile = File(...),
    company_id: str | None = Form(None),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    _session: str = Depends(get_current_session),
) -> SourceUploadResponse:
    """Upload a document and trigger async ingestion."""
    content = (await file.read()).decode("utf-8")
    source_id = await ingestion_service.ingest_upload(
        file_content=content,
        filename=file.filename or "unnamed",
        company_id=company_id,
    )
    await ingestion_queue.enqueue(source_id)
    return SourceUploadResponse(source_id=source_id, status="pending")


@router.get(
    "/companies/{company_id}/sources", response_model=SourceListResponse
)
async def list_sources(
    company_id: UUID,
    status: str = Query("all"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    _session: str = Depends(get_current_session),
) -> SourceListResponse:
    """List all sources for a company with status."""
    items, total = await ingestion_service.list_sources(
        str(company_id), status=status, limit=limit, offset=offset
    )
    return SourceListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[
            SourceListItem(
                source_id=s.id,
                type=s.type,
                subject_or_filename=s.filename_or_subject,
                received_at=s.received_at,
                status=s.status,
                error=s.error,
            )
            for s in items
        ],
    )


@router.get("/sources/{source_id}", response_model=SourceDetail)
async def get_source(
    source_id: UUID,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    _session: str = Depends(get_current_session),
) -> SourceDetail:
    """Get full source detail including raw content."""
    source = await ingestion_service.get_source(str(source_id))
    return SourceDetail(
        source_id=source.id,
        company_id=source.company_id,
        type=source.type,
        subject_or_filename=source.filename_or_subject,
        raw_content=source.raw_content,
        received_at=source.received_at,
        who=source.who,
        interaction_date=source.interaction_date,
        src=source.src,
        status=source.status,
        error=source.error,
    )


@router.get(
    "/sources/{source_id}/status", response_model=SourceStatusResponse
)
async def get_source_status(
    source_id: UUID,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    _session: str = Depends(get_current_session),
) -> SourceStatusResponse:
    """Lightweight status poll."""
    status = await ingestion_service.get_source_status(str(source_id))
    return SourceStatusResponse(source_id=str(source_id), status=status)


@router.post("/sources/{source_id}/retry", response_model=SourceUploadResponse)
async def retry_source(
    source_id: UUID,
    ingestion_service: IngestionService = Depends(get_ingestion_service),
    _session: str = Depends(get_current_session),
) -> SourceUploadResponse:
    """Re-trigger processing of a failed source."""
    await ingestion_service.retry_source(str(source_id))
    return SourceUploadResponse(source_id=str(source_id), status="pending")
