"""
Cortex concept extraction pipeline stage.

Reads chunks for a source, calls Claude tool_use to extract concepts (EXTRACT-01..04),
checks ExtractionCache before every LLM call (EXTRACT-05), runs at most 5 chunks
in parallel via asyncio.Semaphore (EXTRACT-05).

Phase 3 Wave 0: stubs only. Wave 1 implements the bodies.
Phase 3 Wave 1 plan: 03-02-PLAN.md.
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
    """Stub — Wave 1 (Plan 03-02) implements cache lookup + LLM call + cache write.

    Wave 1 implementation outline:
      chunk_hash = hashlib.sha256(chunk.text.encode()).hexdigest()
      async with AsyncSessionLocal() as session:
          cached = await session.scalar(
              sa.select(ExtractionCache).where(
                  ExtractionCache.chunk_hash == chunk_hash,
                  ExtractionCache.model_version == MODEL_VERSION,
              )
          )
          if cached:
              return cached.extracted_concepts or []

      message = await anthropic_client.messages.create(
          model="claude-sonnet-4-6",
          max_tokens=4096,
          tools=[EXTRACT_TOOL],
          tool_choice={"type": "tool", "name": "extract_concepts"},
          messages=[{"role": "user", "content": f"Extract concepts from this chunk:\\n\\n{chunk.text[:8000]}"}],
      )
      if message.stop_reason == "tool_use":
          tool_block = next(b for b in message.content if b.type == "tool_use")
          concepts = tool_block.input.get("concepts", [])
      else:
          # Retry once on end_turn fallback (EXTRACT-04)
          concepts = []
    """
    return []


async def run_extraction(source_id: int) -> None:
    """Stub — Wave 1 (Plan 03-02) implements parallel chunk extraction.

    Wave 1 implementation outline:
      sem = asyncio.Semaphore(5)

      async def extract_one(chunk):
          async with sem:
              return await _extract_chunk_with_cache(chunk, source_type, client)

      results = await asyncio.gather(*[extract_one(c) for c in chunks])
    """
    return None


async def _stage_extract(source_id: int) -> None:
    """Orchestrator-facing alias. pipeline.py calls this name."""
    await run_extraction(source_id)
