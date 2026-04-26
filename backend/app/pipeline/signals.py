"""Struggle signal detection pipeline stage (Phase 4).

Replaces _stage_signals_stub in pipeline.py.
Stage 8 of run_pipeline: detects struggle signals for concepts touched by this source.

Key design decisions (from CONTEXT.md):
- D-07: Recompute only for concepts whose concept_sources include the current source_id
- D-08: STRUGGLE-01 requires chat_log ConceptSources — skip silently if none present
- D-09: STRUGGLE-03 is deterministic string search — no LLM call
- D-10: STRUGGLE-04 checks source.source_metadata["problem_incorrect"]
- D-11: signals dict only includes EVALUATED keys — never set unevaluated keys to False
- STRUGGLE-05: written to concepts.struggle_signals JSONB; flag_modified required
"""
from __future__ import annotations

import math
import sqlalchemy as sa
import sqlalchemy.orm.attributes as _orm_attrs
from openai import AsyncOpenAI
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Chunk, Concept, ConceptSource, Source


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GOTCHA_PHRASES = ["actually,", "common mistake,", "be careful,", "a subtle point"]


# ---------------------------------------------------------------------------
# Cosine similarity helper (math stdlib — no external dependency)
# ---------------------------------------------------------------------------

def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_signals(source_id: int) -> None:
    """Detect and write struggle signals for concepts touched by this source run.

    Stage 8 of run_pipeline. Session-per-stage: opens own AsyncSessionLocal.
    Exceptions bubble up to run_pipeline which writes status=error.
    """
    # Load all concepts touched by this source (D-07: NOT course-wide)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Concept)
            .join(ConceptSource, ConceptSource.concept_id == Concept.id)
            .where(ConceptSource.source_id == source_id)
            .options(
                selectinload(Concept.concept_sources).selectinload(ConceptSource.source)
            )
        )
        concepts = result.scalars().unique().all()

    for concept in concepts:
        await _evaluate_and_write_signals(concept)


# ---------------------------------------------------------------------------
# Per-concept signal evaluation
# ---------------------------------------------------------------------------

async def _evaluate_and_write_signals(concept: Concept) -> None:
    """Evaluate all applicable struggle signals for a single concept and persist.

    DB call order (to match test mock side_effect sequence):
    1. repeated_confusion student questions query (only if chat_log sources exist)
    2. gotcha_dense chunk text query
    3. retention_gap chat_log timestamps query (only if chat_log sources exist)
    4. write signals to DB
    """
    signals: dict = {}  # D-11: only include evaluated keys

    # Determine whether chat_log sources exist for this concept (D-08, D-02)
    has_chat_log_sources = any(
        cs.source and cs.source.source_type == "chat_log"
        for cs in concept.concept_sources
    )

    # -----------------------------------------------------------------------
    # STRUGGLE-01: repeated_confusion — embedding pairwise cosine (D-08)
    # Only evaluate if there are chat_log ConceptSources with student_questions.
    # Query order: FIRST (before gotcha/retention) to match test mock sequencing.
    # -----------------------------------------------------------------------
    if has_chat_log_sources:
        repeated_confusion = await _detect_repeated_confusion(concept)
        if repeated_confusion is not None:
            signals["repeated_confusion"] = repeated_confusion

    # -----------------------------------------------------------------------
    # STRUGGLE-03: gotcha_dense — deterministic string search (D-09, no LLM)
    # -----------------------------------------------------------------------
    gotcha_dense = await _detect_gotcha_dense(concept.id)
    if gotcha_dense is not None:
        signals["gotcha_dense"] = gotcha_dense

    # -----------------------------------------------------------------------
    # STRUGGLE-04: practice_failure — check source metadata flag (D-10)
    # Synchronous — uses already-loaded concept_sources (no extra DB call).
    # -----------------------------------------------------------------------
    practice_failure = _detect_practice_failure(concept)
    if practice_failure is not None:
        signals["practice_failure"] = practice_failure

    # -----------------------------------------------------------------------
    # STRUGGLE-02: retention_gap — two chat_log sources >= 24h apart
    # Only query when chat_log sources exist.
    # Query order: AFTER gotcha, BEFORE write (to match test mock sequencing).
    # -----------------------------------------------------------------------
    if has_chat_log_sources:
        retention_gap = await _detect_retention_gap(concept.id)
        if retention_gap is not None:
            signals["retention_gap"] = retention_gap

    # -----------------------------------------------------------------------
    # Write signals to DB — flag_modified REQUIRED for JSON column mutation
    # -----------------------------------------------------------------------
    async with AsyncSessionLocal() as session:
        db_result = await session.execute(
            sa.select(Concept).where(Concept.id == concept.id)
        )
        db_concept = db_result.scalar_one()
        db_concept.struggle_signals = signals
        _orm_attrs.flag_modified(db_concept, "struggle_signals")  # CRITICAL: SQLAlchemy JSON mutation tracking
        await session.commit()


# ---------------------------------------------------------------------------
# STRUGGLE-01: repeated_confusion
# ---------------------------------------------------------------------------

async def _detect_repeated_confusion(concept: Concept) -> bool | None:
    """Detect if >= 3 student question pairs have cosine similarity > 0.75.

    Only evaluates for concepts with chat_log ConceptSources (D-08).
    Skips silently (returns None) if no chat_log sources or fewer than 3 questions.
    Uses OpenAI text-embedding-3-small (same model as chunk embeddings).
    """
    if not settings.openai_api_key:
        return None  # Skip silently — cannot evaluate without embedding key

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(ConceptSource)
            .join(Source, Source.id == ConceptSource.source_id)
            .where(
                ConceptSource.concept_id == concept.id,
                Source.source_type == "chat_log",
                ConceptSource.student_questions.isnot(None),
            )
        )
        all_questions: list[str] = []
        for cs in result.scalars().all():
            all_questions.extend(cs.student_questions or [])

    if len(all_questions) < 3:
        # Cannot have >= 3 similar pairs with fewer than 3 questions — skip D-08
        return None

    # Embed all questions in one batch OpenAI call
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        embed_resp = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=all_questions,
        )
    except Exception:
        return None  # Skip silently on embedding failure

    vectors = [e.embedding for e in embed_resp.data]

    # Count pairwise similar pairs (O(n^2) — acceptable for < 50 questions in demo scope)
    similar_pairs = sum(
        1
        for i in range(len(vectors))
        for j in range(i + 1, len(vectors))
        if _cosine_sim(vectors[i], vectors[j]) > 0.75
    )

    return similar_pairs >= 3


# ---------------------------------------------------------------------------
# STRUGGLE-03: gotcha_dense
# ---------------------------------------------------------------------------

async def _detect_gotcha_dense(concept_id: int) -> bool | None:
    """Check if any chunk text linked to this concept contains a gotcha trigger phrase.

    Joins: ConceptSource → Source → Chunk via source_id.
    Purely deterministic — no LLM call (D-09).
    Returns None if query returns no rows (no chunks linked).
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Chunk.text)
            .join(Source, Source.id == Chunk.source_id)
            .join(ConceptSource, ConceptSource.source_id == Source.id)
            .where(ConceptSource.concept_id == concept_id)
        )
        chunk_texts = [row.text for row in result.all()]

    if not chunk_texts:
        return None  # No chunks linked — cannot evaluate

    return any(
        phrase in text.lower()
        for text in chunk_texts
        for phrase in GOTCHA_PHRASES
    )


# ---------------------------------------------------------------------------
# STRUGGLE-04: practice_failure
# ---------------------------------------------------------------------------

def _detect_practice_failure(concept: Concept) -> bool | None:
    """Check if any linked source has source_metadata["problem_incorrect"] == True.

    Deterministic check on eagerly-loaded concept_sources (D-10).
    Note: Source.source_metadata is the Python attribute name; mapped to "metadata" column.
    Returns None if concept has no concept_sources (cannot evaluate).
    """
    if not concept.concept_sources:
        return None

    return any(
        (cs.source.source_metadata or {}).get("problem_incorrect") is True
        for cs in concept.concept_sources
    )


# ---------------------------------------------------------------------------
# STRUGGLE-02: retention_gap
# ---------------------------------------------------------------------------

async def _detect_retention_gap(concept_id: int) -> bool | None:
    """Detect if questions about this concept appear in chat_log sources >= 24h apart.

    Uses source.created_at timestamps as session boundaries.
    Returns None if fewer than 2 chat_log sources found (cannot evaluate).
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Source.created_at)
            .join(ConceptSource, ConceptSource.source_id == Source.id)
            .where(
                ConceptSource.concept_id == concept_id,
                Source.source_type == "chat_log",
            )
            .order_by(Source.created_at)
        )
        chat_times = list(result.scalars().all())

    if len(chat_times) < 2:
        return None  # Cannot evaluate — need at least 2 sessions

    for i in range(len(chat_times)):
        for j in range(i + 1, len(chat_times)):
            delta = chat_times[j] - chat_times[i]
            if delta.total_seconds() >= 86400:  # 24h in seconds
                return True

    return False
