from fastapi import APIRouter

from app.api import health, courses, ingest, concepts, quiz

router = APIRouter()

router.include_router(health.router, tags=["health"])
router.include_router(courses.router, prefix="/courses", tags=["courses"])
router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
router.include_router(concepts.router, prefix="/concepts", tags=["concepts"])
router.include_router(quiz.router, prefix="/quiz", tags=["quiz"])
