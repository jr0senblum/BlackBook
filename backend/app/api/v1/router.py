"""Top-level router aggregating all sub-routers."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.companies import router as companies_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(companies_router)
