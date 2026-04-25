from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_session
from app.models.models import Course
from app.schemas.courses import CourseCreate, CourseMatchResponse, CourseResponse

router = APIRouter()

# ---------------------------------------------------------------------------
# GET /courses — list all courses for user_id=1
# ---------------------------------------------------------------------------

@router.get("", response_model=list[CourseResponse])
async def list_courses(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        sa.select(Course).where(Course.user_id == 1).order_by(Course.created_at)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# POST /courses — create a new course
# ---------------------------------------------------------------------------

@router.post("", response_model=CourseResponse, status_code=201)
async def create_course(
    body: CourseCreate,
    session: AsyncSession = Depends(get_session),
):
    course = Course(title=body.title, user_id=body.user_id)
    session.add(course)
    await session.commit()
    await session.refresh(course)
    return course


# ---------------------------------------------------------------------------
# GET /courses/match — cosine similarity pre-flight for Swift notch
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLD = 0.65


@router.get("/match", response_model=Optional[CourseMatchResponse])
async def match_course(hint: str):
    """Embed hint and find best-matching course.

    Returns {course_id, title, confidence} if best confidence >= 0.65.
    Returns null if no courses exist, no course has an embedding, or best < 0.65.
    Contract: null means "user must choose" (D-07).
    """
    if not settings.openai_api_key:
        return None

    # Embed the hint text
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    embed_response = await openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=hint,
    )
    hint_vector = embed_response.data[0].embedding

    # Cosine similarity query via pgvector operator <=>
    # 1 - (embedding <=> hint_vec) = cosine similarity (pgvector returns cosine distance)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.text(
                """
                SELECT id, title, 1 - (embedding <=> CAST(:hint_vec AS vector)) AS confidence
                FROM courses
                WHERE user_id = 1 AND embedding IS NOT NULL
                ORDER BY confidence DESC
                LIMIT 1
                """
            ),
            {"hint_vec": str(hint_vector)},
        )
        row = result.fetchone()

    if row is None or row.confidence < CONFIDENCE_THRESHOLD:
        return None

    return CourseMatchResponse(
        course_id=row.id,
        title=row.title,
        confidence=float(row.confidence),
    )
