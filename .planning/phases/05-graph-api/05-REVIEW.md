---
phase: 05-graph-api
reviewed: 2026-04-25T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - backend/app/api/concepts.py
  - backend/app/api/courses.py
  - backend/app/api/router.py
  - backend/app/schemas/concepts.py
  - backend/app/schemas/graph.py
  - backend/tests/test_concept_detail.py
  - backend/tests/test_graph_api.py
findings:
  critical: 3
  warning: 3
  info: 2
  total: 8
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-04-25T00:00:00Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

This phase implements Graph API endpoints: `GET /courses`, `POST /courses`, `GET /courses/match`, `GET /courses/{course_id}/graph`, and `GET /concepts/{concept_id}`. The overall structure is sound — no N+1 queries, correct synthetic edge assembly, and proper field rename (`definition` → `summary`). However, three blockers were found: a user-controlled `user_id` field in course creation allows ownership spoofing, an unused import of `AsyncSessionLocal` creates an unexplained dependency, and the `_build_graph_payload` function returns a raw `dict` where `GraphResponse` is declared — Pydantic validation is silently bypassed on the return value. Three warnings cover an incomplete OpenAI error handling scope, a double-query ownership check that leaks timing, and inclusion of `struggle_signals` raw data in every concept node in the graph payload.

---

## Critical Issues

### CR-01: User-controlled `user_id` in `POST /courses` allows ownership spoofing

**File:** `backend/app/api/courses.py:39`

**Issue:** `CourseCreate.user_id` defaults to `1` but is a fully client-writable `int` field (schema line 8: `user_id: int = 1`). Any caller that passes `{"title": "x", "user_id": 99}` in the JSON body will create a course owned by user 99. All other endpoints scope reads to `user_id = 1`, so the injected course is unreachable — but it still writes garbage rows to the DB under an arbitrary owner, and it breaks the moment multi-user is added.

```python
# CURRENT (courses.py:39)
course = Course(title=body.title, user_id=body.user_id)

# FIX: ignore client-supplied user_id; pin to 1 (single-user design per CLAUDE.md)
course = Course(title=body.title, user_id=1)
```

If `user_id` is retained in the schema for forward-compat, add a validator or just remove the field from `CourseCreate` entirely and accept only `title`.

---

### CR-02: `_build_graph_payload` returns `dict`, not `GraphResponse` — Pydantic validation is silently bypassed

**File:** `backend/app/api/courses.py:162`

**Issue:** The function signature declares `-> dict`, but the route handler at line 107 declares `response_model=GraphResponse`. FastAPI will call `GraphResponse.model_validate()` on the returned dict only when Pydantic model validation mode is active; however, the function type annotation `-> dict` is misleading and, more critically, if `GraphEdge.type` receives a value outside the documented set (`"contains"`, `"co_occurrence"`, `"prerequisite"`, `"related"`), or if any `data` field contains a non-serialisable value, the error surfaces at serialization time rather than at construction time — making the bug harder to diagnose. The immediate bug is that `GraphEdge.type` is typed as `str` (not `Literal`), so there is no validation gate at all; an edge row with a corrupt `edge_type` goes straight to the client.

Additionally, `GraphNode.data` and `GraphEdge.data` are typed as `dict[str, Any]` which cannot validate that embedding vectors are excluded. The comment "NEVER include embedding vectors" in `graph.py:11` is a convention, not enforced.

```python
# FIX 1: change return type annotation to GraphResponse and construct it
def _build_graph_payload(course, concepts, flashcards, quiz, edges) -> GraphResponse:
    ...
    return GraphResponse(nodes=nodes, edges=graph_edges)
    # Pydantic will validate each GraphNode/GraphEdge at construction time

# FIX 2 (optional hardening): restrict edge type
from typing import Literal
class GraphEdge(BaseModel):
    type: Literal["contains", "co_occurrence", "prerequisite", "related"]
```

---

### CR-03: Unused import of `AsyncSessionLocal` in `courses.py`

**File:** `backend/app/api/courses.py:11`

**Issue:** `AsyncSessionLocal` is imported but never used anywhere in the file. This is not merely a style problem — importing a database session factory that is not used raises the question of whether some code was written (or deleted) that bypassed the dependency-injected `get_session`. If that code path was accidentally removed, data could be written outside the managed transaction. If it was always dead, it is a latent maintenance hazard (future developers may use the imported name incorrectly).

```python
# CURRENT
from app.core.database import AsyncSessionLocal, get_session

# FIX: remove unused import
from app.core.database import get_session
```

---

## Warnings

### WR-01: `GET /concepts/{concept_id}` performs two separate DB round-trips for a single authorization decision

**File:** `backend/app/api/concepts.py:31-45`

**Issue:** The endpoint first fetches the concept row (query 1, line 31-34), then performs a separate ownership query (query 2, lines 39-44). If query 1 returns a concept, an attacker who observes response timing can distinguish "concept exists but is not mine" (two round-trips, 404) from "concept does not exist" (one round-trip, 404). This is a timing side-channel that enables concept-ID enumeration across users. The two queries should be merged.

```python
# FIX: single query that joins concepts + courses and checks both existence and ownership
result = await session.execute(
    sa.select(Concept)
    .join(Course, Concept.course_id == Course.id)
    .where(Concept.id == concept_id, Course.user_id == 1)
)
concept = result.scalar_one_or_none()
if concept is None:
    raise HTTPException(status_code=404, detail="Concept not found")
# ownership is implicit — if concept is None, either it doesn't exist or doesn't belong to user 1
```

---

### WR-02: OpenAI `APIError` catch is too narrow — network errors crash the `match_course` endpoint

**File:** `backend/app/api/courses.py:74`

**Issue:** Only `openai.APIError` is caught. The OpenAI Python SDK raises other exceptions for network-level failures: `openai.APIConnectionError`, `openai.APITimeoutError`, and the base `openai.OpenAIError`. A transient DNS failure or socket timeout will propagate as an unhandled exception, returning a 500 to the client instead of the documented null response.

```python
# CURRENT
except OpenAIError:
    return None

# FIX: catch the broader base exception; OpenAIError is already the base,
# but APIConnectionError / APITimeoutError may not subclass it in all SDK versions.
# Use the safest catch:
import openai
except (openai.APIError, openai.APIConnectionError, openai.APITimeoutError):
    return None
# OR simply:
except Exception:
    return None  # acceptable here since this is a best-effort pre-flight
```

Note: `APIError` is imported as `OpenAIError` (alias at line 7). Confirm the alias covers all desired subclasses by checking the installed SDK version.

---

### WR-03: `struggle_signals` (raw dict) is embedded verbatim in every concept node of the graph payload

**File:** `backend/app/api/courses.py:200`

**Issue:** `c.struggle_signals` is a JSON blob of arbitrary structure written by the pipeline. It is included as-is in every concept node's `data` dict in the graph response. For a course with many concepts, this could include stale or large signal objects. More importantly, the field is not documented as part of the graph node contract in `graph.py`, and its schema is unbounded (`dict | None` in the ORM). If `struggle_signals` grows to include sensitive intermediate data (e.g., raw student question text from a chat log), it will be exposed to any graph consumer.

```python
# FIX: only expose the boolean flag already computed; strip the raw dict
"data": {
    "label": c.title,
    "concept_id": c.id,
    "depth": c.depth,
    "has_struggle_signals": bool(c.struggle_signals),
    # Remove: "struggle_signals": c.struggle_signals,
    "flashcard_count": 0,
},
```

If the raw signals are needed by the frontend, add a dedicated `GET /concepts/{id}/signals` endpoint with proper scoping.

---

## Info

### IN-01: `Optional[CourseMatchResponse]` import from `typing` is redundant with `from __future__ import annotations`

**File:** `backend/app/api/courses.py:3,53`

**Issue:** The file starts with `from __future__ import annotations` (line 1), which makes all annotations strings at runtime. The `Optional` import from `typing` is used only for the `response_model=Optional[CourseMatchResponse]` annotation at line 53. Since `response_model` is evaluated by FastAPI at import time (not as a string annotation), this usage is correct — but the rest of the codebase (e.g., `schemas/concepts.py`, `schemas/courses.py`) uses `str | None` syntax consistently. Using `Optional[...]` here is inconsistent.

```python
# FIX: remove Optional import and use CourseMatchResponse | None
# (FastAPI accepts X | None in response_model on Python 3.10+)
@router.get("/match", response_model=CourseMatchResponse | None)
```

---

### IN-02: Test files duplicate large mock-setup blocks across every test function

**File:** `backend/tests/test_graph_api.py:68-128`, `131-187`, `190-245`, `248-307`, `310-365`

**Issue:** Five graph tests (`test_graph_returns_nodes_and_edges`, `test_graph_node_types_include_course_and_concept`, `test_graph_has_contains_edge`, `test_graph_node_ids_are_prefixed_strings`, `test_graph_endpoint_no_n_plus_one_structural`) each define an identical `mock_course` / `mock_concept` / `mock_session` block — approximately 30 lines duplicated five times. Similarly, four tests in `test_concept_detail.py` repeat the same mock concept setup. This makes future changes to the mock schema error-prone (all five copies must be updated).

```python
# FIX: extract shared fixtures into conftest.py or use pytest parametrize
@pytest_asyncio.fixture
def mock_course():
    c = MagicMock()
    c.id = 1; c.user_id = 1; c.title = "CS229"; c.description = None
    return c
```

---

_Reviewed: 2026-04-25T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
