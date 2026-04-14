"""FastAPI dependency providers."""

from collections.abc import AsyncGenerator

from fastapi import Cookie, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.exceptions import UnauthenticatedError
from app.repositories.action_item_repository import ActionItemRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.credential_repository import CredentialRepository
from app.repositories.functional_area_repository import FunctionalAreaRepository
from app.repositories.inferred_fact_repository import InferredFactRepository
from app.repositories.person_repository import PersonRepository
from app.repositories.relationship_repository import RelationshipRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.source_repository import SourceRepository
from app.services.auth_service import AuthService
from app.services.company_service import CompanyService
from app.services.functional_area_service import FunctionalAreaService
from app.services.inference_service import InferenceService
from app.services.ingestion_service import IngestionService
from app.services.person_service import PersonService
from app.services.review_service import ReviewService
from app.workers.ingestion_worker import IngestionQueue, ingestion_queue

# Database engine and session factory — created once at import time.
engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Singleton InferenceService — shared across requests (stateless, uses
# settings + injected HTTP client).
# ---------------------------------------------------------------------------

_inference_service = InferenceService(settings=settings)


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


async def get_inference_service() -> InferenceService:
    """Provide the singleton InferenceService instance."""
    return _inference_service


def get_ingestion_queue() -> IngestionQueue:
    """Provide the singleton IngestionQueue instance."""
    return ingestion_queue


# ---------------------------------------------------------------------------
# Domain service builders
# ---------------------------------------------------------------------------


def _build_person_service(db: AsyncSession) -> PersonService:
    """Build a PersonService from a session."""
    return PersonService(
        person_repo=PersonRepository(db),
        functional_area_repo=FunctionalAreaRepository(db),
        action_item_repo=ActionItemRepository(db),
        inferred_fact_repo=InferredFactRepository(db),
    )


def _build_functional_area_service(db: AsyncSession) -> FunctionalAreaService:
    """Build a FunctionalAreaService from a session."""
    return FunctionalAreaService(
        area_repo=FunctionalAreaRepository(db),
        person_repo=PersonRepository(db),
        action_item_repo=ActionItemRepository(db),
    )


async def get_person_service(
    db: AsyncSession = Depends(get_db),
) -> PersonService:
    """Provide a PersonService instance for route DI."""
    return _build_person_service(db)


async def get_functional_area_service(
    db: AsyncSession = Depends(get_db),
) -> FunctionalAreaService:
    """Provide a FunctionalAreaService instance for route DI."""
    return _build_functional_area_service(db)


# ---------------------------------------------------------------------------
# ReviewService + IngestionService builders
# ---------------------------------------------------------------------------


async def get_review_service(
    db: AsyncSession = Depends(get_db),
) -> ReviewService:
    """Provide a ReviewService instance."""
    return _build_review_service(db)


def _build_review_service(db: AsyncSession) -> ReviewService:
    """Build a ReviewService from a session (shared by DI and worker)."""
    return ReviewService(
        inferred_fact_repo=InferredFactRepository(db),
        source_repo=SourceRepository(db),
        person_service=_build_person_service(db),
        functional_area_service=_build_functional_area_service(db),
        action_item_repo=ActionItemRepository(db),
        relationship_repo=RelationshipRepository(db),
    )


async def get_ingestion_service(
    db: AsyncSession = Depends(get_db),
) -> IngestionService:
    """Provide an IngestionService instance."""
    return IngestionService(
        source_repo=SourceRepository(db),
        inferred_fact_repo=InferredFactRepository(db),
        company_repo=CompanyRepository(db),
        inference_service=_inference_service,
        review_service=_build_review_service(db),
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
        inference_service=_inference_service,
        review_service=_build_review_service(db),
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
