from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.models import Concept, ConceptSource, Course, Flashcard, Source
from app.schemas.concepts import ConceptDetailResponse, SourceCitation

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /concepts/{concept_id} — full concept detail (GRAPH-04)
# ---------------------------------------------------------------------------

@router.get("/{concept_id}", response_model=ConceptDetailResponse)
async def get_concept_detail(
    concept_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Return full concept detail including summary (mapped from definition),
    aggregated student_questions (chat_log sources only), source_citations,
    and flashcard count.

    Security: validates concept belongs to a course owned by user_id=1 before
    returning data (prevents concept ID enumeration across users).
    """
    # 1. Load concept row
    result = await session.execute(
        sa.select(Concept).where(Concept.id == concept_id)
    )
    concept = result.scalar_one_or_none()
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    # 2. Ownership check: concept must belong to a course owned by user_id=1
    ownership = await session.execute(
        sa.select(Course.id)
        .join(Concept, Concept.course_id == Course.id)
        .where(Concept.id == concept_id, Course.user_id == 1)
    )
    if ownership.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    # 3. Load concept_sources joined with sources (single query — no N+1)
    cs_result = await session.execute(
        sa.select(ConceptSource, Source)
        .join(Source, ConceptSource.source_id == Source.id)
        .where(ConceptSource.concept_id == concept_id)
    )
    cs_rows = cs_result.all()

    # Aggregate student_questions (chat_log sources only) + build source_citations
    student_questions: list[str] = []
    source_citations: list[SourceCitation] = []
    for cs, source in cs_rows:
        if source.source_type == "chat_log" and cs.student_questions:
            student_questions.extend(cs.student_questions)
        source_citations.append(
            SourceCitation(
                source_id=source.id,
                title=source.title,
                source_type=source.source_type,
            )
        )

    # 4. Flashcard count — scalar aggregate (not a list load)
    fc_result = await session.execute(
        sa.select(sa.func.count()).select_from(Flashcard)
        .where(Flashcard.concept_id == concept_id)
    )
    flashcard_count = fc_result.scalar_one()

    # Build response explicitly — do NOT use from_attributes here because
    # Concept.definition must map to response field "summary" (rename at construction).
    # from_attributes would map concept.summary which does not exist → None.
    return ConceptDetailResponse(
        id=concept.id,
        course_id=concept.course_id,
        title=concept.title,
        summary=concept.definition,          # CRITICAL: field rename definition → summary
        key_points=concept.key_points or [],
        gotchas=concept.gotchas or [],
        examples=concept.examples or [],
        student_questions=student_questions,
        source_citations=source_citations,
        flashcard_count=flashcard_count,
        struggle_signals=concept.struggle_signals,
        depth=concept.depth,
    )
