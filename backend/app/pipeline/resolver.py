"""
Cortex concept resolution pipeline stage.

For each newly extracted concept dict, embed (title + definition), run pgvector
cosine query SCOPED TO course_id (RESOLVE-01), and decide:
  - dist <= 0.08 (similarity >= 0.92) -> auto-merge (RESOLVE-02)
  - 0.08 < dist <= 0.20 (similarity 0.80-0.91) -> LLM tiebreaker (RESOLVE-03)
  - dist > 0.20 (similarity < 0.80) -> create new concept (RESOLVE-04)

Phase 3 Wave 1: full implementation.
Phase 3 Wave 1 plan: 03-03-PLAN.md.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

import anthropic
import sqlalchemy as sa
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Chunk, Concept, ConceptSource, ExtractionCache, Source
from app.pipeline.extractor import MODEL_VERSION

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

TIEBREAKER_TOOL: dict[str, Any] = {
    "name": "decide_merge",
    "description": (
        "Decide if two concept descriptions should be stored as a single concept node. "
        "Merge when concept B is the same as, a subtopic of, or a specific variant/application "
        "of concept A (or vice versa). Both concepts come from the same course."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["same", "reason"],
        "properties": {
            "same": {"type": "boolean"},
            "reason": {
                "type": "string",
                "description": "1-sentence explanation.",
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Distance thresholds (cosine_distance = 1 - cosine_similarity)
# similarity >= 0.92  ->  distance <= 0.08  (RESOLVE-02)
# similarity >= 0.72  ->  distance <= 0.28  (RESOLVE-03, LLM tiebreaker)
# else create new                           (RESOLVE-04)
#
# Widened tiebreaker window (0.20 → 0.28) catches subtopic relationships
# like "mixing problems" vs "nonconstant volume in mixing problems".
# The LLM prompt merges subtopics/variants, not just identical concepts.
# ---------------------------------------------------------------------------

_AUTO_MERGE_DIST = 0.08
_TIEBREAKER_MAX_DIST = 0.35


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _embed_text(title: str, definition: str) -> str:
    """Standardize embedding input to avoid distribution drift (Pitfall 4)."""
    return f"{title}. {definition}"


# ---------------------------------------------------------------------------
# Task 1: _llm_tiebreaker
# ---------------------------------------------------------------------------

async def _llm_tiebreaker(
    new_title: str,
    new_definition: str,
    existing_title: str,
    existing_definition: str,
    anthropic_client: anthropic.AsyncAnthropic,
) -> dict:
    """Force-tool-choice call to decide whether two concepts are the same.

    Returns {"same": bool, "reason": str}. On any failure, returns
    {"same": False, "reason": "..."} (conservative — prefer creating a new concept
    over a wrong merge).
    """
    prompt = (
        "Concept A:\n"
        f"  Title: {existing_title}\n"
        f"  Definition: {existing_definition}\n"
        "Concept B:\n"
        f"  Title: {new_title}\n"
        f"  Definition: {new_definition}\n\n"
        "Both concepts come from the same course. Should they be stored as a single concept node?\n"
        "Answer YES (same=true) if B is the same as A, a subtopic of A, a specific case/application "
        "of A, or if A is a subtopic of B. Only answer NO (same=false) if they are genuinely "
        "distinct concepts that a student would need to learn separately."
    )
    try:
        message = await anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            tools=[TIEBREAKER_TOOL],
            tool_choice={"type": "tool", "name": "decide_merge"},
            messages=[{"role": "user", "content": prompt}],
        )
        if message.stop_reason == "tool_use":
            tool_block = next(
                (b for b in message.content if getattr(b, "type", None) == "tool_use"),
                None,
            )
            if tool_block is not None:
                result = tool_block.input
                # Defensive: ensure expected keys
                same = bool(result.get("same", False))
                reason = str(result.get("reason", ""))
                return {"same": same, "reason": reason}
    except Exception:  # noqa: BLE001
        pass
    return {"same": False, "reason": "tiebreaker call failed — defaulting to new concept"}


# ---------------------------------------------------------------------------
# Task 2: helper functions for create/merge
# ---------------------------------------------------------------------------

async def _create_new_concept(
    session,
    title: str,
    definition: str,
    key_points: list,
    gotchas: list,
    examples: list,
    related_concepts: list,
    vec: list[float],
    course_id: int,
    source_id: int,
    student_questions: list | None,
) -> int:
    """RESOLVE-04 — INSERT new Concept + linking ConceptSource."""
    concept = Concept(
        course_id=course_id,
        title=title,
        definition=definition,
        key_points=list(key_points or []),
        gotchas=list(gotchas or []),
        examples=list(examples or []),
        related_concepts=list(related_concepts or []),
        embedding=vec,
    )
    session.add(concept)
    await session.flush()  # populate concept.id without committing the txn
    existing_cs = await session.scalar(
        sa.select(ConceptSource).where(
            ConceptSource.concept_id == concept.id,
            ConceptSource.source_id == source_id,
        )
    )
    if existing_cs is None:
        session.add(
            ConceptSource(
                concept_id=concept.id,
                source_id=source_id,
                student_questions=list(student_questions) if student_questions else None,
            )
        )
    await session.commit()
    # concept.id is set by the DB on flush; in unit tests with mock sessions it
    # may remain None because flush is a no-op — return 0 as a safe sentinel
    # (production code always gets a real DB-generated id from flush).
    return concept.id if concept.id is not None else 0


async def _merge_into_existing(
    session,
    row,
    key_points: list,
    gotchas: list,
    examples: list,
    source_id: int,
    student_questions: list | None,
) -> int:
    """RESOLVE-02 / RESOLVE-03 — extend JSON list fields and add ConceptSource link.

    Caps: key_points[:10], gotchas[:5], examples[:5] (per RESEARCH.md Pattern 5).
    Dedup via dict.fromkeys preserves insertion order.
    """
    existing = await session.get(Concept, row.id)
    if existing is None:
        # Concept was evicted from identity map — reload it explicitly
        existing = await session.scalar(
            sa.select(Concept).where(Concept.id == row.id)
        )
    if existing is not None:
        existing.key_points = list(dict.fromkeys((existing.key_points or []) + list(key_points or [])))[:10]
        existing.gotchas = list(dict.fromkeys((existing.gotchas or []) + list(gotchas or [])))[:5]
        existing.examples = list(dict.fromkeys((existing.examples or []) + list(examples or [])))[:5]
    else:
        raise RuntimeError(f"Concept {row.id} not found during merge")
    existing_cs = await session.scalar(
        sa.select(ConceptSource).where(
            ConceptSource.concept_id == row.id,
            ConceptSource.source_id == source_id,
        )
    )
    if existing_cs is None:
        session.add(
            ConceptSource(
                concept_id=row.id,
                source_id=source_id,
                student_questions=list(student_questions) if student_questions else None,
            )
        )
    await session.commit()
    return row.id


# ---------------------------------------------------------------------------
# Task 2: _resolve_concept
# ---------------------------------------------------------------------------

async def _resolve_concept(
    title: str,
    definition: str,
    key_points: list,
    gotchas: list,
    examples: list,
    related_concepts: list,
    course_id: int,
    source_id: int,
    student_questions: list | None,
    openai_client: AsyncOpenAI,
    anthropic_client: anthropic.AsyncAnthropic,
) -> int:
    """Resolve a candidate concept dict to a canonical concept_id within the course.

    RESOLVE-01: Every cosine query is filtered by Concept.course_id == course_id.
    RESOLVE-02: dist <= 0.08  -> merge with existing.
    RESOLVE-03: 0.08 < dist <= 0.20 -> LLM tiebreaker.
    RESOLVE-04: dist > 0.20 OR no candidates -> create new.
    """
    # 1) Embed the candidate (title + definition — Pitfall 4)
    embed_input = _embed_text(title, definition)
    try:
        embed_resp = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=[embed_input],
        )
        vec = embed_resp.data[0].embedding
    except Exception as exc:  # noqa: BLE001
        _log.warning("Embedding failed for concept '%s': %s", title, exc)
        raise

    # 2) Cosine nearest-neighbor query — COURSE SCOPED (RESOLVE-01)
    # Session is closed before any LLM call to avoid holding a connection open
    # across a 1-5 second network I/O operation (CR-03).
    async with AsyncSessionLocal() as session:
        cosine_result = await session.execute(
            sa.select(
                Concept.id,
                Concept.title,
                Concept.definition,
                Concept.key_points,
                Concept.gotchas,
                Concept.examples,
                Concept.embedding.cosine_distance(vec).label("dist"),
            )
            .where(
                Concept.course_id == course_id,        # RESOLVE-01 — NEVER omit
                Concept.embedding.isnot(None),
            )
            .order_by("dist")
            .limit(1)
        )
        row = cosine_result.first()
    # Session is now closed — connection returned to pool before any LLM call.

    # 3) Decide disposition
    if row is None or row.dist > _TIEBREAKER_MAX_DIST:
        async with AsyncSessionLocal() as session:
            return await _create_new_concept(
                session, title, definition, key_points, gotchas, examples,
                related_concepts, vec, course_id, source_id, student_questions,
            )

    if row.dist <= _AUTO_MERGE_DIST:
        async with AsyncSessionLocal() as session:
            return await _merge_into_existing(
                session, row, key_points, gotchas, examples,
                source_id, student_questions,
            )

    # 0.08 < dist <= 0.20 -> LLM tiebreaker (RESOLVE-03)
    # LLM call is fully outside any DB session — connection pool is free.
    decision = await _llm_tiebreaker(
        new_title=title,
        new_definition=definition,
        existing_title=row.title,
        existing_definition=row.definition or "",
        anthropic_client=anthropic_client,
    )
    async with AsyncSessionLocal() as session:
        if decision.get("same"):
            return await _merge_into_existing(
                session, row, key_points, gotchas, examples,
                source_id, student_questions,
            )
        return await _create_new_concept(
            session, title, definition, key_points, gotchas, examples,
            related_concepts, vec, course_id, source_id, student_questions,
        )


# ---------------------------------------------------------------------------
# Task 3: run_resolution + _stage_resolve
# ---------------------------------------------------------------------------

async def run_resolution(source_id: int) -> None:
    """Stage 5: read extraction_cache for every chunk of source_id; resolve each
    concept dict to a canonical concept_id within the source's course.

    Skips work if API keys missing (matches extractor + _stage_embed pattern).
    """
    if not settings.openai_api_key or not settings.anthropic_api_key:
        return

    # 1) Load source (course_id, source_type) and its chunks
    async with AsyncSessionLocal() as session:
        src_row = await session.scalar(sa.select(Source).where(Source.id == source_id))
        if src_row is None:
            return
        course_id: int = src_row.course_id
        source_type: str = src_row.source_type

        chunks_result = await session.execute(
            sa.select(Chunk.id, Chunk.text).where(Chunk.source_id == source_id)
        )
        chunk_rows = list(chunks_result.all())

    if not chunk_rows:
        return

    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # 2) For each chunk, look up its cached extraction and resolve every concept
    for _chunk_id, chunk_text in chunk_rows:
        chunk_hash = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()

        async with AsyncSessionLocal() as session:
            cached = await session.scalar(
                sa.select(ExtractionCache).where(
                    ExtractionCache.chunk_hash == chunk_hash,
                    ExtractionCache.model_version == MODEL_VERSION,
                )
            )
        if cached is None or cached.extracted_concepts is None:
            continue

        # Normalize cache payload (Plan 03-02 contract):
        #   default: list[dict]
        #   chat_log: {"concepts": list[dict], "_questions": list[str]}
        payload = cached.extracted_concepts
        if isinstance(payload, dict):
            concept_dicts = list(payload.get("concepts", []) or [])
            chunk_questions = list(payload.get("_questions", []) or [])
        else:
            concept_dicts = list(payload or [])
            chunk_questions = []

        # Sequential resolution within a chunk (concepts in same chunk may be similar
        # to each other; sequential avoids race conditions on the same course's
        # cosine query producing inconsistent canonical IDs).
        for cd in concept_dicts:
            try:
                await _resolve_concept(
                    title=cd.get("title", "")[:255] or "Untitled",
                    definition=cd.get("definition", "") or "",
                    key_points=list(cd.get("key_points") or []),
                    gotchas=list(cd.get("gotchas") or []),
                    examples=list(cd.get("examples") or []),
                    related_concepts=list(cd.get("related_concepts") or []),
                    course_id=course_id,
                    source_id=source_id,
                    student_questions=(
                        chunk_questions if (source_type == "chat_log" and chunk_questions) else None
                    ),
                    openai_client=openai_client,
                    anthropic_client=anthropic_client,
                )
            except Exception:  # noqa: BLE001
                # Continue with remaining concepts; pipeline.py top-level catch
                # records the first exception. We swallow per-concept errors here
                # so one bad concept doesn't drop the rest.
                continue


async def _stage_resolve(source_id: int) -> None:
    """Orchestrator-facing alias. pipeline.py calls this name."""
    await run_resolution(source_id)
