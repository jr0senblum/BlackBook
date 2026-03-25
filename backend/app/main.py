"""FastAPI application factory."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.router import router as api_v1_router
from app.exceptions import DomainError


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="BlackBook", version="0.1.0")

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
