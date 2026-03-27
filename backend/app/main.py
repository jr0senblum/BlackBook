"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.router import router as api_v1_router
from app.dependencies import async_session_factory, build_ingestion_service
from app.exceptions import DomainError
from app.workers.ingestion_worker import ingestion_queue


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start background workers on startup, stop on shutdown."""
    # Configure and start the ingestion worker.
    ingestion_queue.configure(
        session_factory=async_session_factory,
        build_ingestion_service=build_ingestion_service,
    )
    await ingestion_queue.start_worker()
    yield
    await ingestion_queue.stop_worker()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="BlackBook", version="0.1.0", lifespan=lifespan)

    # Global exception handler for domain errors → error envelope (§10)
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    app.include_router(api_v1_router, prefix="/api/v1")
    return app


app = create_app()
