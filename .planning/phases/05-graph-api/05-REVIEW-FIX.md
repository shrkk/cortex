---
phase: 05-graph-api
fixed_at: 2026-04-25T00:00:00Z
review_path: .planning/phases/05-graph-api/05-REVIEW.md
iteration: 1
fix_scope: critical_warning
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 05: Code Review Fix Report

**Fixed at:** 2026-04-25T00:00:00Z
**Source review:** `.planning/phases/05-graph-api/05-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 6
- Fixed: 6
- Skipped: 0

## Fixed Issues

### CR-01: User-controlled `user_id` in `POST /courses` allows ownership spoofing

**Files modified:** `backend/app/api/courses.py`
**Commit:** `4336810`
**Applied fix:** Changed `Course(title=body.title, user_id=body.user_id)` to `Course(title=body.title, user_id=1)`. Client-supplied `user_id` is now ignored — the single-user design always pins ownership to user 1, consistent with all read endpoints and the CLAUDE.md single-user design decision.

---

### CR-02: `_build_graph_payload` returns `dict`, not `GraphResponse` — Pydantic validation silently bypassed

**Files modified:** `backend/app/api/courses.py`, `backend/app/schemas/graph.py`
**Commit:** `fe13d32`
**Applied fix:**
1. Changed `_build_graph_payload` return type annotation from `-> dict` to `-> GraphResponse` and updated the return statement to `return GraphResponse(nodes=nodes, edges=graph_edges)`. Pydantic now validates each `GraphNode` and `GraphEdge` at construction time rather than only at serialization.
2. Changed `GraphEdge.type` in `graph.py` from `str` to `Literal["contains", "co_occurrence", "prerequisite", "related"]`. Edge rows with corrupt `edge_type` values are now rejected at the schema boundary rather than passed silently to the client.

---

### CR-03: Unused import of `AsyncSessionLocal` in `courses.py`

**Files modified:** `backend/app/api/courses.py`
**Commit:** `6cfe0c1`
**Applied fix:** Removed `AsyncSessionLocal` from the import line — changed `from app.core.database import AsyncSessionLocal, get_session` to `from app.core.database import get_session`. Eliminates the latent hazard of future developers accidentally using the session factory directly, bypassing the dependency-injected transaction scope.

---

### WR-01: `GET /concepts/{concept_id}` performs two separate DB round-trips for a single authorization decision

**Files modified:** `backend/app/api/concepts.py`
**Commit:** `c255df3`
**Applied fix:** Replaced the two-query pattern (fetch concept, then ownership check) with a single `SELECT Concept JOIN Course WHERE Concept.id = :id AND Course.user_id = 1` query. Both existence and ownership are validated in one round-trip. The timing side-channel is eliminated: "concept does not exist" and "concept exists but not mine" are now indistinguishable (same single-query 404 response path).

---

### WR-02: OpenAI `APIError` catch is too narrow — network errors crash the `match_course` endpoint

**Files modified:** `backend/app/api/courses.py`
**Commit:** `cb2ef19`
**Applied fix:** Added `APIConnectionError` and `APITimeoutError` to the import from `openai`, and broadened the except clause from `except OpenAIError:` to `except (OpenAIError, APIConnectionError, APITimeoutError):`. Transient DNS failures and socket timeouts now return `null` (the documented response) instead of an unhandled 500.

---

### WR-03: `struggle_signals` (raw dict) embedded verbatim in every concept node of graph payload

**Files modified:** `backend/app/api/courses.py`
**Commit:** `4c541fb`
**Applied fix:** Removed the `"struggle_signals": c.struggle_signals` line from the concept node `data` dict in `_build_graph_payload`. The already-computed boolean flag `"has_struggle_signals": bool(c.struggle_signals)` is retained. A comment was added noting that raw signals are intentionally excluded and that a dedicated endpoint should be used for scoped access.

---

## Skipped Issues

None — all in-scope findings were successfully fixed.

---

_Fixed: 2026-04-25T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
