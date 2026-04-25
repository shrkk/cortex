from fastapi import APIRouter

from app.api import health, courses

router = APIRouter()

router.include_router(health.router, tags=["health"])
router.include_router(courses.router, prefix="/courses", tags=["courses"])
