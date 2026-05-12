from __future__ import annotations

import anthropic
import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.models.models import Concept, ConceptSource, Course, Flashcard, Source
from app.schemas.concepts import ConceptDetailResponse, FlashcardResponse, SourceCitation

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /concepts/struggle-flashcards — all flashcards for struggle concepts
# ---------------------------------------------------------------------------

class StruggleFlashcard(FlashcardResponse):
    concept_id: int
    concept_title: str
    course_id: int


@router.get("/struggle-flashcards", response_model=list[StruggleFlashcard])
async def list_struggle_flashcards(
    session: AsyncSession = Depends(get_session),
):
    """Return all flashcards for concepts that have any struggle signal, for user_id=1."""
    rows = await session.execute(
        sa.select(
            Flashcard.id,
            Flashcard.concept_id,
            Flashcard.front,
            Flashcard.back,
            Flashcard.card_type,
            Flashcard.created_at,
            Concept.title.label("concept_title"),
            Concept.course_id,
        )
        .join(Concept, Flashcard.concept_id == Concept.id)
        .join(Course, Concept.course_id == Course.id)
        .where(Course.user_id == 1, Concept.struggle_signals.isnot(None))
        .order_by(Concept.id, Flashcard.id)
    )
    return [
        {
            "id": r.id,
            "concept_id": r.concept_id,
            "front": r.front,
            "back": r.back,
            "card_type": r.card_type,
            "created_at": r.created_at,
            "concept_title": r.concept_title,
            "course_id": r.course_id,
        }
        for r in rows.all()
    ]


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
    # 1. Load concept row + ownership check in a single query (WR-01).
    # Joining Course here eliminates a second round-trip and prevents timing
    # side-channel: attacker cannot distinguish "concept exists but not mine"
    # from "concept does not exist" because both return the same 404.
    result = await session.execute(
        sa.select(Concept)
        .join(Course, Concept.course_id == Course.id)
        .where(Concept.id == concept_id, Course.user_id == 1)
    )
    concept = result.scalar_one_or_none()
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    # 2. Load concept_sources joined with sources (single query — no N+1)
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

    # 3. Flashcard count — scalar aggregate (not a list load)
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


# ---------------------------------------------------------------------------
# GET /concepts/{concept_id}/flashcards — flashcard list for flip mode (UI-06)
# ---------------------------------------------------------------------------

@router.get("/{concept_id}/flashcards", response_model=list[FlashcardResponse])
async def list_concept_flashcards(
    concept_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Return all flashcards for a concept. Ownership check via Course.user_id=1 JOIN.

    Security: 404 on missing or unauthorized concept to prevent ID enumeration (T-06-01-03).
    """
    # Ownership check: concept must belong to a course of user_id=1
    ownership = await session.execute(
        sa.select(Concept)
        .join(Course, Concept.course_id == Course.id)
        .where(Concept.id == concept_id, Course.user_id == 1)
    )
    if ownership.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    result = await session.execute(
        sa.select(Flashcard)
        .where(Flashcard.concept_id == concept_id)
        .order_by(Flashcard.id)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# POST /concepts/{concept_id}/mark-struggle — toggle manual struggle signal
# ---------------------------------------------------------------------------

@router.post("/{concept_id}/mark-struggle")
async def mark_struggle(
    concept_id: int,
    session: AsyncSession = Depends(get_session),
):
    concept = (await session.execute(
        sa.select(Concept).join(Course, Concept.course_id == Course.id)
        .where(Concept.id == concept_id, Course.user_id == 1)
    )).scalar_one_or_none()
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    signals = dict(concept.struggle_signals or {})
    if "manual" in signals:
        signals.pop("manual")
    else:
        signals["manual"] = "Marked as trouble by student"
    concept.struggle_signals = signals or None
    await session.commit()
    return {"struggle_signals": concept.struggle_signals}


# ---------------------------------------------------------------------------
# POST /concepts/{concept_id}/chat — streaming Claude answer with concept ctx
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str


@router.post("/{concept_id}/chat")
async def chat_concept(
    concept_id: int,
    body: ChatRequest,
    session: AsyncSession = Depends(get_session),
):
    concept = (await session.execute(
        sa.select(Concept).join(Course, Concept.course_id == Course.id)
        .where(Concept.id == concept_id, Course.user_id == 1)
    )).scalar_one_or_none()
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    ctx_parts = [f"Concept: {concept.title}"]
    if concept.definition:
        ctx_parts.append(f"Definition: {concept.definition}")
    if concept.key_points:
        ctx_parts.append("Key points:\n" + "\n".join(f"- {p}" for p in concept.key_points))
    if concept.gotchas:
        ctx_parts.append("Common gotchas:\n" + "\n".join(f"- {g}" for g in concept.gotchas))
    context = "\n\n".join(ctx_parts)

    system = (
        "You are Cortex, a concise and precise academic tutor. "
        "Answer the student's question using only the concept context provided. "
        "Be direct and clear. Use LaTeX for any math expressions (inline: $...$, block: $$...$$). "
        "Keep answers under 200 words unless more depth is genuinely needed."
    )
    user_msg = f"{context}\n\n---\nStudent question: {body.question}"

    async def generate():
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        async with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    return StreamingResponse(generate(), media_type="text/plain")
