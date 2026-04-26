---
phase: 05-graph-api
plan: "02"
subsystem: backend-graph-api
tags: [graph-api, fastapi, tdd, green-state, wave-1]
dependency_graph:
  requires:
    - backend/app/schemas/graph.py
    - backend/tests/test_graph_api.py
  provides:
    - backend/app/api/courses.py (GET /courses/{course_id}/graph)
    - backend/app/api/courses.py (_build_graph_payload helper)
  affects:
    - backend/tests/test_graph_api.py
tech_stack:
  added: []
  patterns:
    - "5-query bulk pattern: course → concepts → flashcards IN(concept_ids) → quiz → edges IN(concept_ids)"
    - "Synthetic 'contains' edges built in Python from FK relationships — edges table has no contains rows"
    - "Prefixed node IDs: course-N, concept-N, flashcard-N, quiz-N — avoids React Flow cross-type collisions"
    - "Dependency injection via Depends(get_session) throughout — no direct AsyncSessionLocal() usage"
    - "hint[:500] truncation as DoS mitigation for OpenAI embedding API calls"
key_files:
  created: []
  modified:
    - backend/app/api/courses.py
    - backend/tests/test_graph_api.py
decisions:
  - "Kept AsyncSessionLocal import present (used by other callers elsewhere) but removed direct usage from match_course"
  - "Updated test_graph_api.py match tests to use dependency_overrides[get_session] since implementation no longer uses AsyncSessionLocal"
metrics:
  duration: "240s"
  completed: "2026-04-26"
  tasks_completed: 1
  files_created: 0
  files_modified: 2
---

# Phase 5 Plan 02: Graph API — GET /courses/{id}/graph Implementation Summary

GET /courses/{course_id}/graph implemented with 5-query bulk pattern using SQLAlchemy IN queries; _build_graph_payload synthesizes contains edges from FK relationships; /courses/match refactored to use injected session with hint[:500] DoS truncation; all 10 test_graph_api.py tests GREEN.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add GET /courses/{course_id}/graph route and _build_graph_payload helper to courses.py | 3d3a6ff | backend/app/api/courses.py, backend/tests/test_graph_api.py |

## Verification Results

```
pytest tests/test_graph_api.py -q
→ 10 passed (GREEN state confirmed)

All previously RED tests now GREEN:
- test_graph_returns_nodes_and_edges              (GRAPH-03) PASS
- test_graph_node_types_include_course_and_concept (GRAPH-05) PASS
- test_graph_has_contains_edge                    (GRAPH-05+03) PASS
- test_graph_node_ids_are_prefixed_strings        (GRAPH-05) PASS
- test_graph_endpoint_no_n_plus_one_structural    (GRAPH-06) PASS

Previously passing tests still GREEN:
- test_list_courses_returns_list                  (GRAPH-01) PASS
- test_create_course_returns_id                   (GRAPH-02) PASS
- test_course_match_returns_null_below_threshold  (GRAPH-07) PASS
- test_course_match_returns_match_at_threshold    (GRAPH-07) PASS
- test_course_match_hint_truncated_to_500_chars   (GRAPH-07) PASS
```

Import verification:
```
from app.api.courses import get_course_graph, _build_graph_payload → OK
```

Code verification:
```
hint = hint[:500] present in match_course → OK
async with AsyncSessionLocal() as session: absent from match_course → OK
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated match tests to use dependency_overrides instead of AsyncSessionLocal patch**
- **Found during:** Task 1
- **Issue:** The plan required removing `async with AsyncSessionLocal() as session:` from `match_course`, but `test_course_match_returns_null_below_threshold` and `test_course_match_returns_match_at_threshold` both patched `app.api.courses.AsyncSessionLocal`. With the implementation change, those patches became no-ops — the mock session was never injected, so the tests would attempt a real DB call and fail.
- **Fix:** Rewrote both match tests to use `app.dependency_overrides[get_session]` with try/finally teardown pattern (same pattern used by the graph endpoint tests)
- **Files modified:** `backend/tests/test_graph_api.py`
- **Commit:** 3d3a6ff

## Known Stubs

None. All stubs from Wave 0 replaced with full implementation in this plan.

## Threat Surface Scan

All mitigations from plan threat model are applied:

| Threat ID | Mitigation | Applied |
|-----------|------------|---------|
| T-05-02-01 | `WHERE Course.id == course_id, Course.user_id == 1` → 404 on mismatch | Yes — get_course_graph line ~97 |
| T-05-02-02 | `hint = hint[:500]` before OpenAI call | Yes — match_course line 61 |
| T-05-02-03 | `_build_graph_payload` builds data dict explicitly — embedding never included | Yes — no `concept.embedding` reference in _build_graph_payload |
| T-05-02-04 | hint_vector is parameterized float list from OpenAI, not user input | Accepted — no change needed |
| T-05-02-05 | Structural: exactly 5 queries regardless of data size | Yes — verified by test_graph_endpoint_no_n_plus_one_structural |

No new unplanned network endpoints or security-sensitive data surfaces introduced.

## Self-Check: PASSED

Files verified:
- backend/app/api/courses.py: FOUND (contains get_course_graph, _build_graph_payload, GraphResponse import, hint[:500])
- backend/tests/test_graph_api.py: FOUND (updated match tests)

Commits verified:
- 3d3a6ff: feat(05-02): implement GET /courses/{course_id}/graph + fix /match session injection — FOUND

Test results: 10 passed, 0 failed
