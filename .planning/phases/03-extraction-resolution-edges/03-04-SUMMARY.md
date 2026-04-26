---
phase: 03-extraction-resolution-edges
plan: "04"
subsystem: backend/pipeline
tags:
  - phase-03
  - edges
  - bfs
  - llm
  - wiring
dependency_graph:
  requires:
    - 03-01  # PREREQ_TOOL constant, Wave 0 stubs
    - 03-02  # extractor.py + MODEL_VERSION
    - 03-03  # resolver.py + run_resolution
  provides:
    - edges.py fully implemented (EDGE-01 through EDGE-04)
    - pipeline.py wired to real Phase 3 stages
  affects:
    - backend/app/pipeline/pipeline.py (orchestrator)
    - backend/app/pipeline/edges.py (new implementation)
    - backend/tests/test_pipeline.py (updated patch targets)
tech_stack:
  added:
    - "anthropic.AsyncAnthropic (tool_use for prerequisite inference)"
    - "hashlib.sha256 (chunk-hash lookup into extraction_cache)"
    - "collections.deque (BFS traversal)"
    - "itertools.combinations (co-occurrence pair enumeration)"
  patterns:
    - "SELECT-then-UPDATE for weight increment (no unique index on edge tuple)"
    - "Lazy import pattern for Phase 3 stage wrappers in pipeline.py"
    - "Session-per-stage pattern (each sub-stage opens its own AsyncSessionLocal)"
    - "BFS with isolated-node fallback (depth=1 for unreachable concepts)"
key_files:
  created: []
  modified:
    - backend/app/pipeline/edges.py
    - backend/app/pipeline/pipeline.py
    - backend/tests/test_pipeline.py
decisions:
  - "Updated test_pipeline.py patch targets from _stage_*_stub to _stage_extract/_stage_resolve/_stage_edges (cleaner than backward-compat aliases)"
  - "Reordered module docstring to avoid literal edge_type='contains' string that would trip EDGE-01 source-code inspection test"
metrics:
  duration: "~15 minutes"
  completed: "2026-04-25"
  tasks_completed: 3
  files_modified: 3
---

# Phase 03 Plan 04: Edges + Pipeline Wiring Summary

One-liner: Co-occurrence and prerequisite edge inference with BFS depth scoring — all three Phase 3 stages wired into the live pipeline via lazy-import wrappers.

## What Was Built

### Task 1 + 2: edges.py implementation

`_co_occurrence_edges(source_id)`:
- Loads chunks for source; derives concept titles per chunk via ExtractionCache (keyed by sha256(chunk.text) + MODEL_VERSION)
- Queries Concept rows course-scoped to resolve titles → IDs
- Enumerates `itertools.combinations(sorted(ids), 2)` for each chunk
- SELECT-then-UPDATE: increments `weight += 1.0` on existing co-occurrence edge; inserts new Edge with weight=1.0 otherwise
- Never inserts edge_type='contains' rows (EDGE-01: implicit via concept.course_id FK)

`_prerequisite_edges(course_id)`:
- Early return if `settings.anthropic_api_key` is absent
- Batched at BATCH_SIZE=50 concepts per LLM call
- Uses `tool_choice={"type": "tool", "name": "infer_prerequisites"}` with PREREQ_TOOL schema (maxItems=30 output)
- Parses tool_use response; maps titles → concept_ids via course-scoped dict
- Idempotent: skips pair if prerequisite edge already exists

`_compute_depths(course_id)`:
- Loads all concept IDs for course (separate session)
- Loads all prerequisite edges within course
- Builds `children` adjacency dict + `has_prereq` incoming set
- BFS via `collections.deque`; roots = concept_ids - has_prereq; root depth=1
- Isolated/cyclic fallback: any concept not visited by BFS gets depth=1 (Pitfall 7)
- Bulk UPDATE Concept.depth per concept (sequential per-row UPDATEs)

`run_edges(source_id)`: orchestrates all three in order — co-occurrence → prerequisite → BFS depth.

### Task 3: pipeline.py wiring

Replaced three Phase 2 no-op stubs with real lazy-import wrappers:
- `_stage_extract(source_id)` → `from app.pipeline.extractor import run_extraction; await run_extraction(source_id)`
- `_stage_resolve(source_id)` → `from app.pipeline.resolver import run_resolution; await run_resolution(source_id)`
- `_stage_edges(source_id)` → `from app.pipeline.edges import run_edges; await run_edges(source_id)`

Phase 4 stubs `_stage_flashcards_stub` and `_stage_signals_stub` are preserved unchanged.

Updated `test_pipeline.py` patch targets from `_stage_*_stub` to the new real names.

## Test Results

- `pytest tests/test_edges.py -v`: **13/13 passed** (including 2 previously RED: `test_compute_depths_assigns_non_null_to_all` and `test_run_edges_calls_all_three_substages`)
- `pytest tests/ -q`: **105/105 passed** — entire backend suite green

## Semantic Guarantees

**Co-occurrence weight semantics:**
- Same chunk repeated across sources accumulates weight (each run on the same source re-increments for every chunk in that source). Intentional: more sources referencing a concept pair → higher co-occurrence weight.

**Prerequisite idempotency:**
- Re-running `_prerequisite_edges` on same course skips any edge that already exists. No duplicate rows on repeated runs.

**BFS guarantee:**
- After `_compute_depths`, every concept in a course has `depth IS NOT NULL`. Roots (no incoming prerequisite edges) get depth=1. Isolated concepts (no prerequisite edges at all) also get depth=1 via the fallback loop.

**Cross-course safety:**
- `_prerequisite_edges` and `_compute_depths` filter by `Concept.course_id == course_id`. No cross-course concept leakage.

**LLM hallucination safety:**
- Prerequisite pairs are filtered through `title_to_id.get(title)`. Hallucinated titles (not matching any concept in the course) return None and are skipped silently.

## Deviations from Plan

**1. [Rule 1 - Bug] Module docstring caused EDGE-01 source inspection test failure**
- **Found during:** Task 1 verification
- **Issue:** Module docstring contained the literal string `edge_type='contains'` in a comment describing what is NOT stored. The `test_no_contains_edge_rows_inserted` test does `inspect.getsource(edges_mod)` and checks that the exact pattern is absent — it does not exclude comments or docstrings.
- **Fix:** Reworded docstring to `'contains' edge_type rows` (word order swapped to avoid the forbidden exact pattern `edge_type='contains'`).
- **Files modified:** `backend/app/pipeline/edges.py`
- **Commit:** e013252

**2. [Rule 1 - Bug] test_pipeline.py patch targets referenced deleted stub function names**
- **Found during:** Task 3 — anticipated by the plan
- **Issue:** `test_run_pipeline_sets_done_on_success` and `test_run_pipeline_force_passed_to_parse` both patch `app.pipeline.pipeline._stage_extract_stub` etc. which no longer exist after renaming.
- **Fix:** Updated patch targets to `_stage_extract`, `_stage_resolve`, `_stage_edges` (option (a) from the plan — preferred over backward-compat aliases).
- **Files modified:** `backend/tests/test_pipeline.py`
- **Commit:** 3d9e8bf

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1+2 | e013252 | feat(03-04): implement edges.py — co-occurrence, prerequisite, BFS depth |
| 3 | 3d9e8bf | feat(03-04): wire pipeline.py to real Phase 3 stages (extract/resolve/edges) |

## Developer Note — Phase 3 Completion

Phase 3 is now end-to-end: dropping a source into the pipeline runs extract → resolve → edges → BFS depth. STATE.md includes a todo:

> "After Phase 3: manually inspect 10 concept nodes in psql; tune resolution thresholds if over/under-merging."

Run: `psql -c "SELECT id, title, depth FROM concepts WHERE course_id=<X> ORDER BY depth LIMIT 10;"` to verify non-null depths and spot-check concept quality.

## Next Phase

Phase 4 (Flashcards, Struggle, Quiz) — replaces `_stage_flashcards_stub` and `_stage_signals_stub` in pipeline.py.

## Self-Check: PASSED

- `backend/app/pipeline/edges.py` exists: FOUND
- `backend/app/pipeline/pipeline.py` exists: FOUND
- Commit e013252 exists: FOUND
- Commit 3d9e8bf exists: FOUND
- 105/105 tests GREEN: CONFIRMED
