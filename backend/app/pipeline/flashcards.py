"""Flashcard generation pipeline stage (Phase 4).

Replaces _stage_flashcards_stub in pipeline.py.
Generates 3-6 flashcard nodes per concept via Claude tool_use.
"""
from __future__ import annotations


async def run_flashcards(source_id: int) -> None:
    """Generate flashcards for all concepts touched by this source run.

    Stage 7 of run_pipeline. Session-per-stage: opens own AsyncSessionLocal.
    No-op stub — Wave 1 (04-02-PLAN.md) implements this.
    """
    pass
