"""Struggle signal detection pipeline stage (Phase 4).

Replaces _stage_signals_stub in pipeline.py.
Detects: repeated_confusion, retention_gap, gotcha_dense, practice_failure.
"""
from __future__ import annotations

GOTCHA_PHRASES = ["actually,", "common mistake,", "be careful,", "a subtle point"]


async def run_signals(source_id: int) -> None:
    """Detect and write struggle signals for concepts touched by this source run.

    Stage 8 of run_pipeline. Session-per-stage: opens own AsyncSessionLocal.
    No-op stub — Wave 1 (04-03-PLAN.md) implements this.
    """
    pass
