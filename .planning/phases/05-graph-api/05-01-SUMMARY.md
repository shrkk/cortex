---
phase: 05-graph-api
plan: "01"
subsystem: backend-tests
tags: [tdd, red-state, graph-api, schemas, wave-0]
dependency_graph:
  requires: []
  provides:
    - backend/tests/test_graph_api.py
    - backend/tests/test_concept_detail.py
    - backend/app/schemas/graph.py
    - backend/app/schemas/concepts.py
    - backend/app/api/concepts.py
  affects:
    - backend/app/api/router.py
tech_stack:
  added: []
  patterns:
    - "Pydantic v2 BaseModel without from_attributes for explicitly-constructed responses"
    - "FastAPI router with 501 stub for Wave 0 skeleton"
    - "AsyncMock side_effect list for sequential DB call mocking"
    - "try/finally dependency override teardown to prevent session leakage"
key_files:
  created:
    - backend/tests/test_graph_api.py
    - backend/tests/test_concept_detail.py
    - backend/app/schemas/graph.py
    - backend/app/schemas/concepts.py
    - backend/app/api/concepts.py
  modified:
    - backend/app/api/router.py
decisions:
  - "Register concepts router in router.py during Wave 0 so test can reach the 501 stub (vs 404)"
  - "test_concept_detail_404_for_unknown_id fails in RED state with 501 (not 404) — acceptable since stub always raises before ID check"
metrics:
  duration: "255s"
  completed: "2026-04-26"
  tasks_completed: 2
  files_created: 5
  files_modified: 1
---

# Phase 5 Plan 01: Graph API Wave 0 RED State Summary

Wave 0 Nyquist contract scaffolding: 15 failing test stubs, 2 importable schema files, 1 importable API skeleton. All 7 GRAPH requirements have named failing tests before any production graph code is written.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write RED-state test stubs for graph API (GRAPH-01–07) | 318385f | backend/tests/test_graph_api.py |
| 2 | Write RED-state concept detail tests + schema + API skeleton | 9a3201d | backend/tests/test_concept_detail.py, backend/app/schemas/graph.py, backend/app/schemas/concepts.py, backend/app/api/concepts.py, backend/app/api/router.py |

## Verification Results

```
pytest tests/test_graph_api.py tests/test_concept_detail.py
→ 10 failed, 5 passed (RED state confirmed)

Failures (expected):
- test_graph_returns_nodes_and_edges           (404 — graph endpoint not implemented)
- test_graph_node_types_include_course_and_concept (404)
- test_graph_has_contains_edge                (404)
- test_graph_node_ids_are_prefixed_strings    (404)
- test_graph_endpoint_no_n_plus_one_structural (404)
- test_concept_detail_returns_200             (501 stub)
- test_concept_detail_has_all_required_fields  (501 stub)
- test_concept_detail_summary_maps_from_definition (501 stub)
- test_concept_detail_definition_not_in_response   (501 stub)
- test_concept_detail_404_for_unknown_id      (501 != 404 — stub raises before ID check)

Passes (expected — routes already exist):
- test_list_courses_returns_list              (GRAPH-01)
- test_create_course_returns_id               (GRAPH-02)
- test_course_match_returns_null_below_threshold (GRAPH-07)
- test_course_match_returns_match_at_threshold   (GRAPH-07)
- test_course_match_hint_truncated_to_500_chars  (GRAPH-07)
```

Import verification:
```
from app.schemas.graph import GraphNode, GraphEdge, GraphResponse → OK
from app.schemas.concepts import ConceptDetailResponse, SourceCitation → OK
from app.api.concepts import router → OK
```

## Deviations from Plan

### Auto-added functionality

**1. [Rule 2 - Missing Critical Functionality] Register concepts router in Wave 0**
- **Found during:** Task 2
- **Issue:** Plan spec called for concepts.py skeleton to return 501. Without registering the router in router.py, `GET /concepts/{id}` returns 404 (route not registered) instead of 501 — tests would not reach the skeleton at all
- **Fix:** Added `router.include_router(concepts.router, prefix="/concepts", tags=["concepts"])` to backend/app/api/router.py
- **Files modified:** backend/app/api/router.py
- **Commit:** 9a3201d

## Known Stubs

| Stub | File | Line | Reason |
|------|------|------|--------|
| `raise HTTPException(status_code=501)` | backend/app/api/concepts.py | 19 | Intentional Wave 0 skeleton — full implementation in Wave 1b (05-03-PLAN.md) |

The 501 stub is the entire point of Wave 0: it allows tests to call the endpoint and fail in a meaningful way (501 vs 404) rather than never reaching the skeleton. Wave 1b will replace it with the full implementation.

## Threat Surface Scan

No new network endpoints with security-sensitive data are exposed in this plan. The `GET /concepts/{id}` skeleton endpoint raises 501 unconditionally — no data flows through it until Wave 1b implementation.

The plan's threat model mitigations are correctly applied:
- T-05-W0-01 (test isolation): all tests use try/finally to pop dependency overrides
- T-05-W0-02 (RED state): GRAPH-01/02/07 tests pass (existing routes), GRAPH-03/05/06 fail (graph endpoint 404)

## Self-Check: PASSED
