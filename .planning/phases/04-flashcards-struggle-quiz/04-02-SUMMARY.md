---
plan: 04-02
phase: 04-flashcards-struggle-quiz
status: complete
completed: 2026-04-25
---

# Plan 04-02: Flashcard Generation Implementation

## What Was Built

Implemented `backend/app/pipeline/flashcards.py` — the real flashcard generation pipeline stage that replaces the Wave 0 no-op stub. Wired into pipeline.py stage 7.

## Key Files

### Created/Modified
- `backend/app/pipeline/flashcards.py` — Full implementation with FLASHCARD_TOOL schema, run_flashcards(), _call_llm()
- `backend/app/pipeline/pipeline.py` — Stage 7 wired via lazy import of run_flashcards
- `backend/tests/test_flashcards.py` — xfail markers removed, all 8 tests now PASS

## Self-Check: PASSED

All must_haves verified:
- ✓ run_flashcards(source_id) generates Flashcard rows per concept touched by source_id via Claude tool_use
- ✓ Concepts with existing flashcards are skipped (selectinload + len check)
- ✓ asyncio.Semaphore(3) enforced for max 3 parallel LLM calls
- ✓ FLASHCARD_TOOL with additionalProperties: false and all 4 card_type enum values
- ✓ pipeline.py stage 7 wired via lazy import
- ✓ All 8 FLASH tests PASS (8 passed, 0 failed, exit 0)

## Test Results

```
tests/test_flashcards.py::test_no_srs_columns PASSED
tests/test_flashcards.py::test_flashcard_has_required_columns PASSED
tests/test_flashcards.py::test_flashcard_generation PASSED
tests/test_flashcards.py::test_card_types PASSED
tests/test_flashcards.py::test_idempotency PASSED
tests/test_flashcards.py::test_flashcards_uses_semaphore PASSED
tests/test_flashcards.py::test_flashcards_uses_tool_choice PASSED
tests/test_flashcards.py::test_flashcards_uses_selectinload PASSED
8 passed, 1 warning in 0.21s
```

## Key Decisions

- `_call_llm()` extracted as separate async function (testable + clean retry logic)
- Two-attempt retry with silent skip on second failure (pipeline resilience)
- Separate AsyncSessionLocal for read and write to avoid session contamination
- `result.scalars().unique().all()` — `.unique()` required to prevent JOIN duplicates
