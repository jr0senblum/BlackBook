"""FastAPI dependency providers."""

from collections.abc import AsyncGenerator

from fastapi import Cookie, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.exceptions import UnauthenticatedError
from app.repositories.company_repository import CompanyRepository
from app.repositories.credential_repository import CredentialRepository
from app.repositories.inferred_fact_repository import InferredFactRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.source_repository import SourceRepository
from app.services.auth_service import AuthService
from app.services.company_service import CompanyService
from app.services.ingestion_service import IngestionService
from app.workers.ingestion_worker import IngestionQueue, ingestion_queue

# Database engine and session factory — created once at import time.
engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Stub services for InferenceService and ReviewService (not yet implemented).
# These will be replaced when Units 2 and 5 are implemented.
# ---------------------------------------------------------------------------


class _StubInferenceService:
    async def extract_facts(self, lines):
        raise NotImplementedError(
            "InferenceService not yet implemented (Unit 2)"
        )


class _StubReviewService:
    async def save_facts(self, source_id, company_id, facts):
        raise NotImplementedError(
            "ReviewService not yet implemented (Unit 5)"
        )


_stub_inference_service = _StubInferenceService()
_stub_review_service = _StubReviewService()


# ---------------------------------------------------------------------------
# Dependency providers
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session per request."""
    async with async_session_factory() as session:
        async with session.begin():
            yield session


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """Provide an AuthService instance."""
    return AuthService(
        credential_repo=CredentialRepository(db),
        session_repo=SessionRepository(db),
        settings=settings,
    )


async def get_company_service(db: AsyncSession = Depends(get_db)) -> CompanyService:
    """Provide a CompanyService instance."""
    return CompanyService(company_repo=CompanyRepository(db))


async def get_source_repository(
    db: AsyncSession = Depends(get_db),
) -> SourceRepository:
    """Provide a SourceRepository instance."""
    return SourceRepository(db)


async def get_inferred_fact_repository(
    db: AsyncSession = Depends(get_db),
) -> InferredFactRepository:
    """Provide an InferredFactRepository instance."""
    return InferredFactRepository(db)


async def get_inference_service() -> _StubInferenceService:
    """Provide an InferenceService instance.

    Returns a stub until Unit 2 is implemented. Will be replaced with the
    real InferenceService that accepts Settings + HTTP client.
    """
    return _stub_inference_service


def get_ingestion_queue() -> IngestionQueue:
    """Provide the singleton IngestionQueue instance."""
    return ingestion_queue


async def get_ingestion_service(
    db: AsyncSession = Depends(get_db),
) -> IngestionService:
    """Provide an IngestionService instance.

    InferenceService and ReviewService are not yet implemented (Units 2 & 5).
    They are wired as stubs here — the upload/routing/source-CRUD paths work
    without them, and process_source (called by the background worker) will
    use the real implementations once they exist.
    """
    return IngestionService(
        source_repo=SourceRepository(db),
        inferred_fact_repo=InferredFactRepository(db),
        company_repo=CompanyRepository(db),
        inference_service=_stub_inference_service,
        review_service=_stub_review_service,
        ingestion_queue=ingestion_queue,
        settings=settings,
    )


def build_ingestion_service(db: AsyncSession) -> IngestionService:
    """Build an IngestionService for use by the background worker.

    Same wiring as get_ingestion_service but without FastAPI Depends.
    """
    return IngestionService(
        source_repo=SourceRepository(db),
        inferred_fact_repo=InferredFactRepository(db),
        company_repo=CompanyRepository(db),
        inference_service=_stub_inference_service,
        review_service=_stub_review_service,
        ingestion_queue=ingestion_queue,
        settings=settings,
    )


async def get_current_session(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> str:
    """Validate the session cookie. Returns the session token on success.

    Raises UnauthenticatedError (401) if the cookie is missing, invalid, or expired.
    """
    token = request.cookies.get("session")
    await auth_service.validate_session(token)
    return token
