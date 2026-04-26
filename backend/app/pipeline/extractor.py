"""
Cortex concept extraction pipeline stage.

Reads chunks for a source, calls Claude tool_use to extract concepts (EXTRACT-01..04),
checks ExtractionCache before every LLM call (EXTRACT-05), runs at most 5 chunks
in parallel via asyncio.Semaphore (EXTRACT-05).

Phase 3 Wave 1: full implementation (Plan 03-02).
"""
from __future__ import annotations

import asyncio
import hashlib
import re
from typing import Any

import anthropic
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Chunk, Concept, ConceptSource, ExtractionCache, Source

# Bump the trailing :vN whenever the EXTRACT_TOOL prompt or schema changes,
# OR run TRUNCATE extraction_cache; — see RESEARCH.md Pitfall 2.
MODEL_VERSION: str = "claude-sonnet-4-6:v1"

# Cache payload contract:
#   default: list[dict]  — list of concept dicts
#   chat_log: {"concepts": list[dict], "_questions": list[str]}
# Plan 03-03 (resolver) normalizes both shapes.

EXTRACT_TOOL: dict[str, Any] = {
    "name": "extract_concepts",
    "description": (
        "Extract 0-6 specific academic concepts from this text chunk. "
        "Do NOT extract generic study skills (e.g., 'Problem Solving', 'Note Taking', "
        "'Time Management'), acronym-only concepts (e.g., 'NN', 'ML', 'GD'), procedural "
        "steps (e.g., 'Step 1', 'Algorithm Overview'), or course logistics. Extract only "
        "concrete technical concepts a student would need to understand and be tested on."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["concepts"],
        "properties": {
            "concepts": {
                "type": "array",
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "title",
                        "definition",
                        "key_points",
                        "gotchas",
                        "examples",
                        "related_concepts",
                    ],
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": (
                                "Title Case, singular, canonical. E.g., 'Gradient Descent' "
                                "not 'GD' or 'gradient descent optimization procedure'."
                            ),
                        },
                        "definition": {
                            "type": "string",
                            "description": "1-3 sentence definition.",
                        },
                        "key_points": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "3-5 bullet points a student must know.",
                        },
                        "gotchas": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Common mistakes or misconceptions.",
                        },
                        "examples": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Concrete examples or applications.",
                        },
                        "related_concepts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Titles of related concepts mentioned in chunk.",
                        },
                    },
                },
            }
        },
    },
}


def _extract_questions(text: str) -> list[str]:
    """Regex-extract verbatim questions from chat_log chunks (EXTRACT-03)."""
    return [q.strip() for q in re.findall(r"[^.!?\n]*\?", text) if q.strip()]


async def _extract_chunk_with_cache(
    chunk: Chunk,
    source_type: str,
    anthropic_client: anthropic.AsyncAnthropic,
) -> list[dict]:
    """Extract concepts from a chunk with ExtractionCache lookup.

    EXTRACT-04: tool_use with additionalProperties:false; retry once on parse failure.
    EXTRACT-05: cache check before every LLM call (PIPE-04).
    """
    chunk_hash = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()

    # 1) Cache lookup
    async with AsyncSessionLocal() as session:
        cached = await session.scalar(
            sa.select(ExtractionCache).where(
                ExtractionCache.chunk_hash == chunk_hash,
                ExtractionCache.model_version == MODEL_VERSION,
            )
        )
        if cached is not None:
            return list(cached.extracted_concepts or [])

    # 2) LLM call (outside session — pure I/O). Retry exactly once on parse failure.
    concepts: list[dict] = []
    for attempt in range(2):  # initial + 1 retry == 2 attempts max
        try:
            message = await anthropic_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                tools=[EXTRACT_TOOL],
                tool_choice={"type": "tool", "name": "extract_concepts"},
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Extract concepts from this lecture chunk. "
                            f"Source type: {source_type}.\n\n"
                            f"{chunk.text[:8000]}"
                        ),
                    }
                ],
            )
            if message.stop_reason == "tool_use":
                tool_block = next(
                    (b for b in message.content if getattr(b, "type", None) == "tool_use"),
                    None,
                )
                if tool_block is not None:
                    concepts = list(tool_block.input.get("concepts", []) or [])
                    break  # success
            # stop_reason was 'end_turn' or no tool_use block — fall through to retry
            concepts = []
        except Exception:  # noqa: BLE001 — defensive against SDK churn
            concepts = []
            # retry

    # 3) Cache write (UPSERT on (chunk_hash, model_version) unique index)
    async with AsyncSessionLocal() as session:
        stmt = pg_insert(ExtractionCache).values(
            chunk_hash=chunk_hash,
            model_version=MODEL_VERSION,
            extracted_concepts=concepts,
        ).on_conflict_do_update(
            index_elements=["chunk_hash", "model_version"],
            set_={"extracted_concepts": concepts},
        )
        await session.execute(stmt)
        await session.commit()

    return concepts


async def run_extraction(source_id: int) -> None:
    """Stage 4 of the pipeline: extract concepts from every chunk of `source_id`.

    Concurrency: max 5 chunks at once (asyncio.Semaphore(5)) — EXTRACT-05.
    Cache: every chunk's extraction is upserted to extraction_cache by
    _extract_chunk_with_cache itself.
    Resolver (Plan 03-03) reads back via the same chunk_hash + MODEL_VERSION key.

    Skips work if ANTHROPIC_API_KEY is not configured (matches _stage_embed
    'no-API-key skip' pattern in pipeline.py).
    """
    if not settings.anthropic_api_key:
        return

    # Load source + chunks
    async with AsyncSessionLocal() as session:
        src_row = await session.scalar(sa.select(Source).where(Source.id == source_id))
        if src_row is None:
            return
        source_type = src_row.source_type

        chunks_result = await session.execute(
            sa.select(Chunk).where(Chunk.source_id == source_id)
        )
        chunks: list[Chunk] = list(chunks_result.scalars().all())

    if not chunks:
        return

    anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    sem = asyncio.Semaphore(5)

    async def _extract_one(c: Chunk) -> None:
        async with sem:
            await _extract_chunk_with_cache(c, source_type, anthropic_client)
            # For chat_log sources, augment the cache row with verbatim questions
            # so the resolver (Plan 03-03) can populate ConceptSource.student_questions.
            if source_type == "chat_log":
                questions = _extract_questions(c.text)
                if questions:
                    chunk_hash = hashlib.sha256(c.text.encode("utf-8")).hexdigest()
                    async with AsyncSessionLocal() as session:
                        cached = await session.scalar(
                            sa.select(ExtractionCache).where(
                                ExtractionCache.chunk_hash == chunk_hash,
                                ExtractionCache.model_version == MODEL_VERSION,
                            )
                        )
                        if cached is not None:
                            payload = cached.extracted_concepts
                            # Normalize: wrap list payload into dict so we can attach
                            # questions without breaking downstream readers.
                            if isinstance(payload, list):
                                wrapped: dict = {"concepts": payload, "_questions": questions}
                            elif isinstance(payload, dict):
                                wrapped = dict(payload)
                                wrapped["_questions"] = questions
                            else:
                                wrapped = {"concepts": [], "_questions": questions}
                            await session.execute(
                                sa.update(ExtractionCache)
                                .where(
                                    ExtractionCache.chunk_hash == chunk_hash,
                                    ExtractionCache.model_version == MODEL_VERSION,
                                )
                                .values(extracted_concepts=wrapped)
                            )
                            await session.commit()

    await asyncio.gather(*[_extract_one(c) for c in chunks])


async def _stage_extract(source_id: int) -> None:
    """Orchestrator-facing alias. pipeline.py calls this name."""
    await run_extraction(source_id)
