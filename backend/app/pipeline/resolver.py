"""
Cortex concept resolution pipeline stage.

For each newly extracted concept dict, embed (title + definition), run pgvector
cosine query SCOPED TO course_id (RESOLVE-01), and decide:
  - dist <= 0.08 (similarity >= 0.92) -> auto-merge (RESOLVE-02)
  - 0.08 < dist <= 0.20 (similarity 0.80-0.91) -> LLM tiebreaker (RESOLVE-03)
  - dist > 0.20 (similarity < 0.80) -> create new concept (RESOLVE-04)

Phase 3 Wave 0: stubs only. Wave 1 implements the bodies.
Phase 3 Wave 1 plan: 03-03-PLAN.md.
"""
from __future__ import annotations

from typing import Any

import anthropic
import sqlalchemy as sa
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Concept, ConceptSource, Source

TIEBREAKER_TOOL: dict[str, Any] = {
    "name": "decide_merge",
    "description": (
        "Decide if two concept descriptions refer to the same academic concept. "
        "Both concepts come from the same course."
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


async def _llm_tiebreaker(
    new_title: str,
    new_definition: str,
    existing_title: str,
    existing_definition: str,
    anthropic_client: anthropic.AsyncAnthropic,
) -> dict:
    """Stub — Wave 1 implements forced tool_use call returning {same, reason}."""
    return {"same": False, "reason": "stub"}


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
    """Stub — Wave 1 implements embed + cosine + merge/create. Returns canonical concept_id.

    Resolution is strictly course-scoped — RESOLVE-01:
    cosine query MUST include Concept.course_id == course_id filter at all times.
    Embedding strategy: f"{title}. {definition}" to prevent Pitfall 4.

    Wave 1 implementation outline:
      embed_text = f"{title}. {definition}"
      embed_resp = await openai_client.embeddings.create(
          model="text-embedding-3-small",
          input=[embed_text],
      )
      vec = embed_resp.data[0].embedding

      async with AsyncSessionLocal() as session:
          rows = (await session.execute(
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
                  Concept.course_id == course_id,   # RESOLVE-01: MUST have this
                  Concept.embedding.isnot(None),
              )
              .order_by("dist")
              .limit(1)
          )).first()

          if rows is None or rows.dist > 0.20:
              # RESOLVE-04: new concept
              concept = Concept(course_id=course_id, ...)
              session.add(concept)
              await session.flush()
              session.add(ConceptSource(concept_id=concept.id, source_id=source_id))
              await session.commit()
              return concept.id
          elif rows.dist <= 0.08:
              # RESOLVE-02: auto-merge
              await session.commit()
              return rows.id
          else:
              # RESOLVE-03: LLM tiebreaker
              tiebreaker = await _llm_tiebreaker(
                  title, definition, rows.title, rows.definition, anthropic_client
              )
              if tiebreaker["same"]:
                  await session.commit()
                  return rows.id
              else:
                  concept = Concept(course_id=course_id, ...)
                  session.add(concept)
                  await session.flush()
                  await session.commit()
                  return concept.id
    """
    return 0


async def run_resolution(source_id: int) -> None:
    """Stub — Wave 1 implements: load extracted_concepts from extraction_cache for this
    source's chunks, then for each concept dict call _resolve_concept and link via
    ConceptSource."""
    return None


async def _stage_resolve(source_id: int) -> None:
    """Orchestrator-facing alias. pipeline.py calls this name."""
    await run_resolution(source_id)
