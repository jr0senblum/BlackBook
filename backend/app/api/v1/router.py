"""Top-level router aggregating all sub-routers."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.companies import router as companies_router
from app.api.v1.facts import router as facts_router
from app.api.v1.pending import router as pending_router
from app.api.v1.people import router as people_router
from app.api.v1.sources import router as sources_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(companies_router)
router.include_router(facts_router)
router.include_router(pending_router)
router.include_router(people_router)
router.include_router(sources_router)
