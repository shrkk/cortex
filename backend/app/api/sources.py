from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.models import Source, Course
from app.schemas.courses import SourceResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /sources — all sources for user_id=1 (library page)
# ---------------------------------------------------------------------------

@router.get("", response_model=list[SourceResponse])
async def list_sources(session: AsyncSession = Depends(get_session)):
    """Return all sources belonging to courses owned by user_id=1.
    Used by the library page which shows a unified view across all courses.
    """
    result = await session.execute(
        sa.select(Source)
        .join(Course, Source.course_id == Course.id)
        .where(Course.user_id == 1)
        .order_by(Source.created_at.desc())
    )
    return result.scalars().all()
