---
phase: 04-flashcards-struggle-quiz
plan: "01"
subsystem: backend
tags: [tdd, red-state, stubs, flashcards, signals, quiz]
dependency_graph:
  requires: []
  provides:
    - backend/app/pipeline/flashcards.py (run_flashcards stub)
    - backend/app/pipeline/signals.py (run_signals stub, GOTCHA_PHRASES)
    - backend/app/api/quiz.py (router stub, _strip_reference_answers)
    - backend/app/schemas/quiz.py (QuizCreate, QuizResponse, AnswerRequest, AnswerResponse)
    - backend/tests/test_flashcards.py (RED stubs FLASH-01 to FLASH-06)
    - backend/tests/test_signals.py (RED stubs STRUGGLE-01 to STRUGGLE-05)
    - backend/tests/test_quiz_api.py (RED stubs QUIZ-01 to QUIZ-06)
  affects:
    - backend/app/api/router.py (quiz router can now be registered by Wave 2)
    - backend/app/pipeline/pipeline.py (run_flashcards/run_signals can replace stubs in Wave 1)
tech_stack:
  added: []
  patterns:
    - TDD RED state — xfail markers for async implementation tests
    - Structural tests that verify model schema and pure logic pass immediately in RED
    - Source inspection tests (Semaphore, tool_choice, flag_modified) deferred to xfail since Wave 1 adds them
key_files:
  created:
    - backend/app/pipeline/flashcards.py
    - backend/app/pipeline/signals.py
    - backend/app/api/quiz.py
    - backend/app/schemas/quiz.py
    - backend/tests/test_flashcards.py
    - backend/tests/test_signals.py
    - backend/tests/test_quiz_api.py
  modified: []
decisions:
  - "Source inspection tests (Semaphore, tool_choice, selectinload, flag_modified) marked xfail rather than failing hard — Wave 1 adds these keywords to the implementations"
metrics:
  duration: "~8 minutes"
  completed_date: "2026-04-25"
  tasks_completed: 2
  files_created: 7
  files_modified: 0
---

# Phase 4 Plan 01: RED State Scaffolding Summary

**One-liner:** Seven new files establish TDD RED boundary — 3 test files (27 tests: 10 pass, 17 xfail) + 4 importable module stubs for flashcards, signals, quiz router, and quiz schemas.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create module stubs | ea3b501 | flashcards.py, signals.py, quiz.py, schemas/quiz.py |
| 2 | Create RED test stubs | ae0b82f | test_flashcards.py, test_signals.py, test_quiz_api.py |

## Verification

```
cd backend && python -m pytest tests/test_flashcards.py tests/test_signals.py tests/test_quiz_api.py -v
```

Result: **10 passed, 17 xfailed, 0 failed** — exit code 0.

### Structural tests passing (RED state):
- `test_no_srs_columns` — Flashcard has no due_at, ease_factor, repetitions (FLASH-06)
- `test_flashcard_has_required_columns` — Flashcard has concept_id, front, back, card_type (FLASH-03)
- `test_gotcha_dense_detects_phrases` — GOTCHA_PHRASES contains all 4 trigger phrases (STRUGGLE-03)
- `test_gotcha_phrase_detection_case_insensitive` — case-insensitive detection logic (STRUGGLE-03)
- `test_signals_omits_unevaluated_keys` — signal dict omits keys not evaluated (D-11)
- `test_quiz_model` — Quiz has course_id, no concept_id, has questions column (QUIZ-01)
- `test_no_reference_answer_in_quiz_response` — _strip_reference_answers removes secret field (QUIZ-05/T-04-01)
- `test_strip_handles_empty_list` — edge case: empty/None input returns []
- `test_question_distribution_formula` — D-16 formula: round(N*0.4) MCQ, round(N*0.3) short_answer (QUIZ-03)
- `test_quiz_router_registered` — router is an APIRouter instance (QUIZ-02)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Source inspection tests marked xfail instead of passing immediately**
- **Found during:** Task 2 verification — pytest run showed 4 unexpected FAILs
- **Issue:** `test_flashcards_uses_semaphore`, `test_flashcards_uses_tool_choice`, `test_flashcards_uses_selectinload`, `test_signals_uses_flag_modified` check for keywords (`Semaphore(3)`, `tool_choice`, `generate_flashcards`, `selectinload`, `flag_modified`) that exist only after Wave 1 implements the pipeline functions. The plan's code block did not include `@pytest.mark.xfail` on these tests, but they cannot pass in RED state.
- **Fix:** Added `@pytest.mark.xfail(strict=True, reason="RED — Wave 1 (...) adds X to Y")` to all 4 tests.
- **Files modified:** backend/tests/test_flashcards.py, backend/tests/test_signals.py
- **Commit:** ae0b82f

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundaries introduced. The quiz router stub is not yet registered in `app/api/router.py` — Wave 2 (04-04) will add it. The `_strip_reference_answers` security invariant is verified by `test_no_reference_answer_in_quiz_response` (T-04-01 mitigated in RED state).

## Self-Check: PASSED

Files created:
- FOUND: backend/app/pipeline/flashcards.py
- FOUND: backend/app/pipeline/signals.py
- FOUND: backend/app/api/quiz.py
- FOUND: backend/app/schemas/quiz.py
- FOUND: backend/tests/test_flashcards.py
- FOUND: backend/tests/test_signals.py
- FOUND: backend/tests/test_quiz_api.py

Commits:
- FOUND: ea3b501 (feat(04-01): create module stubs)
- FOUND: ae0b82f (test(04-01): add RED test stubs)
