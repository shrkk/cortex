"""Flashcard generation pipeline stage (Phase 4).

Replaces _stage_flashcards_stub in pipeline.py.
Stage 7 of run_pipeline: generates 3-6 flashcard nodes per concept via Claude tool_use.

Key design decisions (from CONTEXT.md):
- D-01: One LLM call per concept; returns all cards as JSON array via tool_use
- D-02: Gotcha cards are one per entry in concept.gotchas (can exceed 6 total)
- D-03: Minimum 2 cards per concept (definition + application), always
- D-04: Skip concepts that already have flashcards (idempotency)
- D-05: Max 3 parallel LLM calls via asyncio.Semaphore(3)
- D-06: Operates on concepts touched by current source_id via ConceptSource join
"""
from __future__ import annotations

import asyncio
import anthropic
import sqlalchemy as sa
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Concept, ConceptSource, Flashcard


# ---------------------------------------------------------------------------
# Tool schema — additionalProperties: false enforces strict JSON Schema (EXTRACT-04 convention)
# ---------------------------------------------------------------------------

FLASHCARD_TOOL = {
    "name": "generate_flashcards",
    "description": (
        "Generate study flashcards for this concept. "
        "Always include at minimum a definition card and an application card (D-03). "
        "Include one gotcha card per distinct gotcha entry in the concept (D-02). "
        "Include a compare card only if the concept has obvious related concepts to compare against. "
        "The 3-6 total cap applies only to definition + application + compare cards; "
        "gotcha cards are additional and do not count toward the cap."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["cards"],
        "properties": {
            "cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["front", "back", "card_type"],
                    "properties": {
                        "front": {
                            "type": "string",
                            "description": "Question or prompt side of the card"
                        },
                        "back": {
                            "type": "string",
                            "description": "Answer or explanation side of the card"
                        },
                        "card_type": {
                            "type": "string",
                            "enum": ["definition", "application", "gotcha", "compare"]
                        }
                    }
                }
            }
        }
    }
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_flashcards(source_id: int) -> None:
    """Generate flashcards for all concepts touched by this source run.

    Stage 7 of run_pipeline. Session-per-stage: opens own AsyncSessionLocal.
    Exceptions bubble up to run_pipeline which writes status=error.
    """
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    sem = asyncio.Semaphore(3)  # D-05: max 3 parallel LLM calls

    # Load all concepts touched by this source, with flashcards eager-loaded for D-04 check
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Concept)
            .join(ConceptSource, ConceptSource.concept_id == Concept.id)
            .where(ConceptSource.source_id == source_id)
            .options(selectinload(Concept.flashcards))  # REQUIRED: async raises MissingGreenlet on lazy load
        )
        concepts = result.scalars().unique().all()  # .unique() prevents duplicates from JOIN

    async def generate_one(concept: Concept) -> None:
        async with sem:
            if concept.flashcards:  # D-04: skip if already has flashcards
                return
            cards = await _call_llm(concept, client)
            if not cards:
                return
            async with AsyncSessionLocal() as session:
                for card in cards:
                    session.add(Flashcard(
                        concept_id=concept.id,
                        front=card["front"],
                        back=card["back"],
                        card_type=card["card_type"],
                    ))
                await session.commit()

    await asyncio.gather(*[generate_one(c) for c in concepts])


# ---------------------------------------------------------------------------
# LLM call helper
# ---------------------------------------------------------------------------

async def _call_llm(concept: Concept, client: anthropic.AsyncAnthropic) -> list[dict]:
    """Call Claude tool_use for a single concept, return list of card dicts.

    Returns [] on LLM failure (stop_reason != tool_use after one retry).
    Does NOT raise — failed concept is silently skipped.
    """
    user_content = (
        f"Concept: {concept.title}\n"
        f"Definition: {concept.definition or '(none)'}\n"
        f"Gotchas: {concept.gotchas or []}\n"
        f"Related concepts: {concept.related_concepts or []}\n\n"
        f"Generate flashcards for this concept. Always include at least a definition card "
        f"and an application card. Add one gotcha card per distinct gotcha listed above. "
        f"Add a compare card only if related concepts are present."
    )
    for attempt in range(2):  # one retry on parse failure
        try:
            message = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                tools=[FLASHCARD_TOOL],
                tool_choice={"type": "tool", "name": "generate_flashcards"},
                messages=[{"role": "user", "content": user_content}]
            )
            if message.stop_reason == "tool_use":
                tool_block = next(b for b in message.content if b.type == "tool_use")
                cards = tool_block.input.get("cards", [])  # already Python list — no json.loads
                return cards
        except Exception:
            if attempt == 1:
                return []  # second failure — skip concept silently
    return []
