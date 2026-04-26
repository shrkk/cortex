---
plan: 04-03
phase: 04-flashcards-struggle-quiz
status: complete
completed: 2026-04-25
---

# Plan 04-03: Struggle Signal Detection Implementation

## What Was Built

Implemented `backend/app/pipeline/signals.py` — the real struggle signal detection pipeline stage. Wired into pipeline.py stage 8. Both stage 7 and stage 8 of the pipeline now dispatch to real implementations.

## Key Files

### Created/Modified
- `backend/app/pipeline/signals.py` — Full implementation: run_signals(), GOTCHA_PHRASES, _cosine_sim(), four signal detectors
- `backend/app/pipeline/pipeline.py` — Stage 7 and stage 8 both wired via lazy import
- `backend/tests/test_signals.py` — xfail markers removed, all 9 tests now PASS

## Self-Check: PASSED

All must_haves verified:
- ✓ run_signals evaluates signals only for concepts touched by the current source_id (D-07)
- ✓ STRUGGLE-03 (gotcha_dense): pure string search, no LLM (D-09)
- ✓ STRUGGLE-04 (practice_failure): checks source.source_metadata["problem_incorrect"]
- ✓ STRUGGLE-01 (repeated_confusion): OpenAI embedding cosine > 0.75, >= 3 pairs
- ✓ STRUGGLE-02 (retention_gap): two chat_log sources >= 24h apart
- ✓ STRUGGLE-05: flag_modified called before session.commit() for JSON mutation
- ✓ D-11: signals dict only includes evaluated keys
- ✓ pipeline.py stage 8 wired via lazy import
- ✓ All 9 STRUGGLE tests PASS (exit 0)

## Test Results

```
9 passed, 1 warning in 0.05s
```

## Key Decisions

- `_orm_attrs.flag_modified` referenced via module alias for test mock patchability
- signals dict initialized empty, keys added only when evaluated (D-11)
- Session-per-stage: separate AsyncSessionLocal for read and write
