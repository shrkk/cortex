from fastapi import APIRouter

from app.api import health

router = APIRouter()

# Phase 2+ will add more routers here:
# router.include_router(courses.router, prefix="/courses", tags=["courses"])
# router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
router.include_router(health.router, tags=["health"])
