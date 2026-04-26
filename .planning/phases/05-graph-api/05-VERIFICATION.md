---
phase: 05-graph-api
verified: 2026-04-26T02:42:14Z
status: human_needed
score: 7/7 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run all 7 curl smoke tests against the live API: GET /courses, POST /courses, GET /courses/{id}/graph (check node_types includes course+concept, edge_types includes contains), GET /concepts/{id} (check summary field present, definition absent), GET /courses/match?hint=backpropagation, GET /courses/99999/graph (expect 404), GET /concepts/99999 (expect 404)"
    expected: "All 7 curl tests match expected outputs described in 05-04-PLAN.md Task 2. node_types includes course and concept. edge_types includes contains. /concepts/{id} response has summary (non-null) and no definition key. /match returns null for nonsense hint. 404 guards return correct detail strings."
    why_human: "Full end-to-end behavior against a live DB with seed data cannot be verified programmatically without starting the server and loading seed data. Unit tests mock all DB calls. GRAPH-07 confidence test (>= 0.65 returns match) requires a real OpenAI key and a course with a computed embedding vector."
---

# Phase 5: Graph API Verification Report

**Phase Goal:** All backend API contracts are stable and return correctly shaped graph payloads — course nodes, concept nodes, flashcard nodes, quiz nodes, all edges, and course-matching — so the frontend can be built against them without rework.
**Verified:** 2026-04-26T02:42:14Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /courses/{id}/graph returns 200 with nodes[] and edges[] for a valid course_id | VERIFIED | `test_graph_returns_nodes_and_edges` PASS; `get_course_graph` in courses.py lines 107-159 returns GraphResponse; live test with `_build_graph_payload` confirmed correct structure |
| 2 | Returned nodes include types: course, concept, flashcard, quiz (when they exist) | VERIFIED | `test_graph_node_types_include_course_and_concept` PASS; live `_build_graph_payload` call returns `{'course', 'flashcard', 'quiz', 'concept'}`; `_build_graph_payload` has explicit construction for all 4 node types |
| 3 | Returned edges include type contains (synthetic from concept.course_id FK) | VERIFIED | `test_graph_has_contains_edge` PASS; `_build_graph_payload` synthesizes contains edges in Python from FK; confirmed "contains" in edge_types on live call |
| 4 | All node id values are prefixed strings: course-N, concept-N, flashcard-N, quiz-N | VERIFIED | `test_graph_node_ids_are_prefixed_strings` PASS; live call returns `['course-1', 'concept-10', 'flashcard-5', 'quiz-3']`; f-string prefixes in `_build_graph_payload` lines 175, 191, 214, 244 |
| 5 | No concept.embedding vector data appears in any node's data dict | VERIFIED | `grep -n "\.embedding" courses.py` returns only match_course embed_response (not in `_build_graph_payload`); data dicts in `_build_graph_payload` built explicitly with named fields only — no wildcard or `.embedding` reference |
| 6 | GET /courses/match truncates hint to 500 chars and uses injected session dependency | VERIFIED | `hint = hint[:500]` at courses.py line 61; `session: AsyncSession = Depends(get_session)` in function signature line 54; `async with AsyncSessionLocal()` not present in match_course; all 3 GRAPH-07 tests PASS |
| 7 | Graph endpoint issues exactly 5 execute() calls for a course with 1 concept | VERIFIED | `test_graph_endpoint_no_n_plus_one_structural` PASS; `mock_session.execute.call_count == 5` asserted; 5-query pattern confirmed in courses.py: course → concepts → flashcards IN(concept_ids) → quiz → edges IN(concept_ids) |
| 8 | GET /concepts/{id} returns HTTP 200 with all required GRAPH-04 fields | VERIFIED | All 5 `test_concept_detail_*` tests PASS; `ConceptDetailResponse` has all fields: id, course_id, title, summary, key_points, gotchas, examples, student_questions, source_citations, flashcard_count, struggle_signals, depth |
| 9 | response.summary equals the value stored in concept.definition (rename is applied) | VERIFIED | `test_concept_detail_summary_maps_from_definition` PASS; `summary=concept.definition` at concepts.py line 83; no `from_attributes` that could silently mis-map |
| 10 | response does not contain a key named definition | VERIFIED | `test_concept_detail_definition_not_in_response` PASS; `ConceptDetailResponse.model_fields` contains no "definition" key (confirmed by import check) |
| 11 | GET /concepts/{id} returns HTTP 404 for unknown concept | VERIFIED | `test_concept_detail_404_for_unknown_id` PASS; `raise HTTPException(status_code=404, detail="Concept not found")` at concepts.py line 36 |
| 12 | student_questions is aggregated only from ConceptSource rows where source.source_type == 'chat_log' | VERIFIED | `source.source_type == "chat_log"` filter at concepts.py line 59; student_questions only extended for matching rows |
| 13 | flashcard_count is a COUNT aggregate | VERIFIED | `sa.func.count()` at concepts.py line 71; scalar aggregate, not list length |
| 14 | concepts router is registered at /concepts prefix in router.py | VERIFIED | router.py line 10: `router.include_router(concepts.router, prefix="/concepts", tags=["concepts"])`; live route check confirms `/concepts/{concept_id}` in app routes |
| 15 | Full pytest suite exits 0 (all tests GREEN) | VERIFIED | `python -m pytest tests/ -q` → 147 passed, 0 failures |

**Score:** 7/7 roadmap success criteria verified (15 derived must-haves all VERIFIED)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/api/courses.py` | GET /courses/{course_id}/graph + _build_graph_payload | VERIFIED | Contains `async def get_course_graph(`, `def _build_graph_payload(`, `from app.schemas.graph import GraphResponse`, `from app.models.models import Course, Concept, Flashcard, Quiz, Edge` |
| `backend/app/api/concepts.py` | Full GET /concepts/{concept_id} (replaces 501 stub) | VERIFIED | Contains `async def get_concept_detail(`, `summary=concept.definition`, `source.source_type == "chat_log"`, `sa.func.count()`, NO `status_code=501` |
| `backend/app/schemas/graph.py` | GraphNode, GraphEdge, GraphResponse Pydantic v2 models | VERIFIED | All 3 classes present; correct field types; no from_attributes |
| `backend/app/schemas/concepts.py` | SourceCitation, ConceptDetailResponse Pydantic v2 models | VERIFIED | `summary: str \| None = None` present; `class SourceCitation(BaseModel)` present; no "definition" field |
| `backend/app/api/router.py` | concepts router registered at /concepts prefix | VERIFIED | `from app.api import health, courses, ingest, concepts, quiz`; `router.include_router(concepts.router, prefix="/concepts"...)` |
| `backend/tests/test_graph_api.py` | 10 tests covering GRAPH-01,02,03,05,06,07 | VERIFIED | 10 test functions confirmed; all 10 PASS |
| `backend/tests/test_concept_detail.py` | 5 tests covering GRAPH-04 | VERIFIED | 5 test functions confirmed; all 5 PASS |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `backend/app/api/courses.py` | `backend/app/schemas/graph.py` | `from app.schemas.graph import GraphResponse` | WIRED | Present at courses.py line 14; used as `response_model=GraphResponse` at line 107 |
| `backend/app/api/courses.py` | `backend/app/models/models.py` | `from app.models.models import Course, Concept, Flashcard, Quiz, Edge` | WIRED | Present at courses.py line 12; all 5 models used in get_course_graph queries |
| `backend/app/api/concepts.py` | `backend/app/schemas/concepts.py` | `from app.schemas.concepts import ConceptDetailResponse` | WIRED | Present at concepts.py line 9; used as `response_model=ConceptDetailResponse` at line 18 |
| `backend/app/api/router.py` | `backend/app/api/concepts.py` | `include_router` at `/concepts` prefix | WIRED | router.py line 10; `/concepts/{concept_id}` confirmed in app routes list |
| `backend/tests/test_graph_api.py` | `backend/app/api/courses.py` | `client.get('/courses/1/graph')` | WIRED | 5 graph tests call `/courses/1/graph`; all PASS meaning route is reached |
| `backend/tests/test_concept_detail.py` | `backend/app/api/concepts.py` | `client.get('/concepts/5')` | WIRED | All 5 concept tests call `/concepts/5`; all PASS |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `get_course_graph` | nodes, edges | 5 SQLAlchemy queries (course, concepts, flashcards, quiz, edges) | Yes — queries against real ORM models; `_build_graph_payload` assembles from query results | FLOWING |
| `get_concept_detail` | ConceptDetailResponse | 4 SQLAlchemy queries (concept, ownership, concept_sources JOIN, flashcard COUNT) | Yes — explicit field construction from query results; `summary=concept.definition` not from static value | FLOWING |
| `match_course` | CourseMatchResponse or None | OpenAI embedding API + pgvector cosine similarity SQL | Yes — real DB query with `1 - (embedding <=> CAST(:hint_vec AS vector))`; returns None when key absent or confidence < 0.65 | FLOWING (with graceful degradation when OpenAI key unavailable) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 15 graph+concept tests GREEN | `python -m pytest tests/test_graph_api.py tests/test_concept_detail.py -v` | 15 passed, 0 failed | PASS |
| Full suite GREEN | `python -m pytest tests/ -q` | 147 passed, 0 failed | PASS |
| All imports resolve | `python -c "from app.schemas.graph import GraphNode, GraphEdge, GraphResponse; from app.schemas.concepts import ConceptDetailResponse, SourceCitation; from app.api.concepts import router; from app.api.courses import get_course_graph, _build_graph_payload"` | "All imports OK" | PASS |
| Route registration order (/match before /{course_id}/graph) | `python -c "from app.api.courses import router; print([r.path for r in router.routes])"` | `['', '', '/match', '/{course_id}/graph']` | PASS |
| _build_graph_payload produces all 4 node types | Live function call with mock course+concept+flashcard+quiz | `{'course', 'flashcard', 'quiz', 'concept'}` in node_types; quiz connected to course root via contains edge; flashcard connected to concept via contains edge | PASS |
| ConceptDetailResponse fields | `python -c "from app.schemas.concepts import ConceptDetailResponse; print(list(ConceptDetailResponse.model_fields.keys()))"` | Contains summary, no definition | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| GRAPH-01 | 05-01, 05-02, 05-04 | GET /courses returns all courses for user | SATISFIED | `list_courses` in courses.py; `test_list_courses_returns_list` PASS |
| GRAPH-02 | 05-01, 05-02, 05-04 | POST /courses creates course with id | SATISFIED | `create_course` in courses.py; `test_create_course_returns_id` PASS |
| GRAPH-03 | 05-01, 05-02, 05-04 | GET /courses/{id}/graph returns all node types + edges | SATISFIED | `get_course_graph` + `_build_graph_payload` in courses.py; `test_graph_returns_nodes_and_edges` PASS |
| GRAPH-04 | 05-01, 05-03, 05-04 | GET /concepts/{id} returns full concept detail with summary field | SATISFIED | `get_concept_detail` in concepts.py; all 5 test_concept_detail tests PASS |
| GRAPH-05 | 05-01, 05-02, 05-04 | Graph node types: course, concept, flashcard, quiz | SATISFIED | All 4 node types synthesized in `_build_graph_payload`; `test_graph_node_types_include_course_and_concept` + `test_graph_node_ids_are_prefixed_strings` PASS |
| GRAPH-06 | 05-01, 05-02, 05-04 | No N+1 (backend: 5 fixed queries); frontend polling is Phase 6 (UI-11) | SATISFIED (backend portion) | `test_graph_endpoint_no_n_plus_one_structural` PASS; flashcard+edge loading via IN queries on concept_ids |
| GRAPH-07 | 05-01, 05-02, 05-04 | GET /courses/match returns match or null based on 0.65 threshold | SATISFIED | `match_course` in courses.py with `hint[:500]`, `CONFIDENCE_THRESHOLD=0.65`, OpenAIError→None; 3 GRAPH-07 tests PASS |

All 7 GRAPH requirement IDs from PLAN frontmatter (05-01 through 05-04) are covered. No orphaned requirements found — REQUIREMENTS.md maps GRAPH-01 through GRAPH-07 exclusively to Phase 5.

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `backend/app/api/courses.py` | `AsyncSessionLocal` imported but not used in match_course | Info | Import is kept for other callers; not a functional issue — match_course correctly uses `Depends(get_session)` |

No stubs, no TODO/FIXME markers, no hardcoded empty returns, no `return null` in production paths in the key Phase 5 files.

### Human Verification Required

#### 1. End-to-End Smoke Test Against Live API

**Test:** Start the API server (`docker compose up -d && cd backend && uvicorn app.main:app --reload`) with a seeded DB, then run the 7 curl smoke tests from 05-04-PLAN.md Task 2.

**Expected:**
- `GET /courses` returns a list with at least 1 course
- `POST /courses` returns `{id, title}` with non-null id
- `GET /courses/1/graph` returns `node_types` including "course" and "concept"; `edge_types` including "contains"; all node ids are prefixed strings
- `GET /concepts/<id>` returns all required keys including "summary" (non-null for concepts with definitions); "definition" key must NOT be present
- `GET /courses/match?hint=backpropagation` returns `{course_id, title, confidence}` when CS229 seed data is loaded (requires real OpenAI key + seeded DB)
- `GET /courses/99999/graph` returns `{"detail": "Course not found"}`
- `GET /concepts/99999` returns `{"detail": "Concept not found"}`

**Why human:** Unit tests mock all DB calls — no test exercises a real DB query path. GRAPH-07 confidence test (confidence >= 0.65 returns match object) requires a real OpenAI API key and a course row with a computed `embedding` vector in the DB. The `_build_graph_payload` function's live behavior with real ORM objects (not MagicMock) has not been exercised programmatically without a running server.

### Gaps Summary

No gaps found. All 7 GRAPH roadmap success criteria are verified against the actual codebase. The single human verification item is for live-API smoke testing with a real DB and OpenAI key — all code paths are substantively implemented and wired.

**GRAPH-06 scope note:** The requirement text "Graph polls for updates every 5s on the frontend" is a frontend behavior assigned to Phase 6 (UI-11). Phase 5 delivers the backend side: the graph endpoint itself with no N+1 queries (5 fixed execute calls regardless of data size), verified structurally by `test_graph_endpoint_no_n_plus_one_structural`.

---

_Verified: 2026-04-26T02:42:14Z_
_Verifier: Claude (gsd-verifier)_
