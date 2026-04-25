---
phase: 2
plan: "02-03"
subsystem: backend-api
tags: [courses, api, embeddings, pgvector, openai, tdd]
dependency_graph:
  requires: ["02-01"]
  provides: ["GET /courses", "POST /courses", "GET /courses/match"]
  affects: ["02-06", "02-07", "02-08"]
tech_stack:
  added: ["openai AsyncOpenAI client", "pgvector cosine similarity query"]
  patterns: ["FastAPI APIRouter with prefix", "dependency_overrides for test isolation", "TDD RED/GREEN cycle"]
key_files:
  created:
    - backend/app/schemas/courses.py
    - backend/app/api/courses.py
    - backend/tests/test_courses.py
  modified:
    - backend/app/api/router.py
decisions:
  - "Use dependency_overrides in tests for create endpoints to avoid FK constraint against users table in test DB"
  - "Declare /courses/match before parameterized routes so FastAPI does not treat 'match' as a path param"
  - "AsyncSessionLocal used directly in match endpoint (raw SQL cosine query); get_session dependency used for CRUD"
  - "CAST(:hint_vec AS vector) required because SQLAlchemy passes Python list as string; pgvector needs explicit cast"
metrics:
  duration: "3 minutes"
  completed: "2026-04-25T23:37:00Z"
  tasks_completed: 3
  files_changed: 4
  tests_added: 7
  tests_passing: 7
---

# Phase 2 Plan 03: Course Endpoints Summary

**One-liner:** FastAPI course API (GET/POST/match) with pgvector cosine similarity for Swift notch pre-flight matching at confidence threshold 0.65.

## Tasks Completed

| Task | Description | Commit | Type |
|------|-------------|--------|------|
| 1 | Create CourseCreate, CourseResponse, CourseMatchResponse Pydantic schemas | 07781a5 | feat |
| 2 (RED) | Write failing tests for all 7 course endpoint behaviors | 53f3403 | test |
| 2 (GREEN) | Implement courses.py with GET/POST/match endpoints | cb783ba | feat |
| 3 | Wire courses.router to main router with prefix="/courses" | 7c51383 | feat |

## What Was Built

Three course endpoints powering the Swift notch pre-flight flow:

- **GET /courses** — lists all courses for user_id=1, ordered by created_at
- **POST /courses** — creates a course (title + user_id=1 default), returns 201 with full course object
- **GET /courses/match?hint=text** — embeds the hint via `text-embedding-3-small`, runs pgvector cosine similarity query against `courses.embedding`, returns `{course_id, title, confidence}` if confidence >= 0.65, or `null` otherwise

The match endpoint returns `null` in three safe cases: no OpenAI key configured, no courses with embeddings, or best confidence below 0.65.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test isolation for POST /courses — FK violation against users table**

- **Found during:** Task 2 GREEN phase
- **Issue:** `POST /courses` with real DB failed with `ForeignKeyViolationError` because user_id=1 is not present in the test database's `users` table. The plan's acceptance criteria required testing create behavior.
- **Fix:** Used FastAPI `dependency_overrides` to replace `get_session` with a mock session in the two create tests. The mock session's `refresh()` populates `id` and `created_at` on the ORM object, making `CourseResponse.model_validate()` succeed without hitting the real DB.
- **Files modified:** `backend/tests/test_courses.py`
- **Commit:** cb783ba

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (test) | 53f3403 | All 7 tests failed as expected |
| GREEN (feat) | cb783ba | All 7 tests pass |
| REFACTOR | — | Not needed — implementation was clean |

## Known Stubs

None — all three endpoints return real data from the database or properly gated null responses.

## Threat Flags

No new trust boundaries introduced beyond what was modeled in the plan's STRIDE register:
- T-02-03-01: SQL injection via title — mitigated by Pydantic + SQLAlchemy parameterized queries
- T-02-03-02: SQL injection via hint vector — mitigated by bound parameter + explicit CAST
- T-02-03-03: OpenAI key — never logged, instantiated inside function scope
- T-02-03-04: DoS via OpenAI call — accepted (local dev, URL query string bounded)
- T-02-03-05: user_id hardcoded to 1 — accepted (single-user by design)

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| backend/app/schemas/courses.py exists | FOUND |
| backend/app/api/courses.py exists | FOUND |
| backend/tests/test_courses.py exists | FOUND |
| Commit 07781a5 (schemas) | FOUND |
| Commit 53f3403 (TDD RED) | FOUND |
| Commit cb783ba (TDD GREEN) | FOUND |
| Commit 7c51383 (router) | FOUND |
| All 7 tests passing | VERIFIED |
