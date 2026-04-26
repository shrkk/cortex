---
plan: 04-04
phase: 04-flashcards-struggle-quiz
status: complete
completed: 2026-04-26
subsystem: backend/quiz-api
tags: [quiz, fastapi, llm, tool_use, grading, wave-2]
dependency-graph:
  requires: [04-02, 04-03]
  provides: [POST /quiz, GET /quiz/{id}/results, POST /quiz/{id}/answer]
  affects: [router.py, quiz.py]
tech-stack:
  added: []
  patterns: [tool_use forced grading, flag_modified JSON mutation, module-ref settings mock]
key-files:
  created: []
  modified:
    - backend/app/api/quiz.py
    - backend/app/api/router.py
    - backend/tests/test_quiz_api.py
decisions:
  - "Use _orm_attrs.flag_modified (module ref) instead of direct import — required for test mock patchability via sqlalchemy.orm.attributes.flag_modified"
  - "Use import app.core.config as _config / _config.settings.anthropic_api_key — required for test patch via app.core.config.settings"
  - "xfail markers removed from 5 integration tests (test_create_quiz, test_quiz_results, test_answer_persisted, test_free_response_grading, test_question_distribution) — all now PASS"
metrics:
  duration: "~10 minutes"
  completed: "2026-04-26"
  tasks: 2
  files_modified: 3
---

# Phase 04 Plan 04: Quiz API Implementation Summary

## What Was Built

Full implementation of three quiz API endpoints in `backend/app/api/quiz.py`, replacing stubs with production-ready code. Registered the quiz router in `router.py`. All 10 QUIZ tests now pass.

One-liner: Quiz API with D-16 distribution, D-18 priority sorting, D-19 Claude tool_use grading, and D-12 flag_modified JSON mutation — all 10 QUIZ tests pass.

## Key Files

### Modified
- `backend/app/api/quiz.py` — Full implementation: POST /quiz, GET /quiz/{id}/results, POST /quiz/{id}/answer, plus helpers _strip_reference_answers, _question_distribution, _grade_free_response, _generate_quiz_questions
- `backend/app/api/router.py` — Added quiz router import and include_router at prefix=/quiz
- `backend/tests/test_quiz_api.py` — Removed xfail markers from 5 integration tests (now all PASS)

## Test Results

```
tests/test_quiz_api.py — 10 passed
Full suite (excluding DB-dependent): 142 passed, 1 pre-existing failure (test_retention_gap in test_signals.py — existed at f0a5b79 before this plan)
```

## Must-Haves Verified

- POST /quiz with {course_id, num_questions} returns 201 with quiz_id and questions stripped of reference_answer
- Quiz question types follow D-16 distribution: round(N*0.4) MCQ, round(N*0.3) short_answer, remainder application
- POST /quiz/{id}/answer grades MCQ deterministically and free-response via Claude tool_use
- POST /quiz/{id}/answer mutates quiz.questions in-place via _orm_attrs.flag_modified before commit
- POST /quiz/{id}/answer returns is_complete=True + score + concepts_to_review when last question answered (D-13)
- GET /quiz/{id}/results returns same shape as terminal answer response (D-14)
- reference_answer stripped in ALL three response paths via _strip_reference_answers()
- num_questions capped at len(concepts) * 2 before LLM call
- router.py registers quiz.router at prefix=/quiz
- All 10 QUIZ tests pass (exit 0)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Module-level settings access for test patchability**
- **Found during:** Task 1 — test_create_quiz failing with 503 (settings check not using mock)
- **Issue:** Direct `from app.core.config import settings` import creates a local name that ignores `with patch("app.core.config.settings")` in tests
- **Fix:** Changed to `import app.core.config as _config` and `_config.settings.anthropic_api_key` throughout
- **Files modified:** backend/app/api/quiz.py
- **Commit:** d6edcb7

**2. [Rule 1 - Bug] flag_modified module reference for test patchability**
- **Found during:** Task 1 — test_answer_persisted failing because mock_flag_modified.assert_called() saw 0 calls
- **Issue:** Direct `from sqlalchemy.orm.attributes import flag_modified` import creates a local name that ignores `with patch("sqlalchemy.orm.attributes.flag_modified")` in tests
- **Fix:** Changed to `import sqlalchemy.orm.attributes as _orm_attrs` and `_orm_attrs.flag_modified(quiz, "questions")` (same pattern used by signals.py)
- **Files modified:** backend/app/api/quiz.py
- **Commit:** d6edcb7

**3. [Rule 1 - Bug] xfail markers removed from test_quiz_api.py**
- **Found during:** Initial test run — test_question_distribution XPASS(strict) caused failure
- **Issue:** Tests had `xfail(strict=True)` markers from RED phase; implementation makes them PASS so strict xfail converts to FAIL
- **Fix:** Removed xfail decorators from all 5 integration tests
- **Files modified:** backend/tests/test_quiz_api.py
- **Commit:** d6edcb7

## Deferred Issues

**Pre-existing failure: test_signals.py::test_retention_gap**
- This test was already failing at commit f0a5b79 (before this plan began)
- The 04-03 SUMMARY claims "9 STRUGGLE tests PASS" but test_retention_gap fails
- Not related to quiz API changes — out of scope for this plan
- Logged to deferred-items for follow-up

## Commits

| Hash | Message |
|------|---------|
| d6edcb7 | feat(04-04): implement quiz.py — POST /quiz, GET /quiz/{id}/results, POST /quiz/{id}/answer |
| 1938f26 | feat(04-04): register quiz router in router.py at prefix=/quiz |

## Known Stubs

None — all three endpoints fully implemented and tested.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes beyond what the plan's threat_model documented (T-04-10 through T-04-15). All mitigations applied:
- T-04-10: _strip_reference_answers() called in all three response paths
- T-04-11: num_questions capped at len(concepts) * 2
- T-04-12: _orm_attrs.flag_modified called before every session.commit()
- T-04-13: strip().lower() normalization on MCQ comparison

## Self-Check: PASSED

- backend/app/api/quiz.py exists and contains async def create_quiz, quiz_results, answer_question
- backend/app/api/router.py contains quiz.router registration
- Commits d6edcb7 and 1938f26 exist in git log
- All 10 tests in tests/test_quiz_api.py pass (exit 0)
