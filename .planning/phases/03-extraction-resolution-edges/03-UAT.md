---
status: complete
phase: 03-extraction-resolution-edges
source: [03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md, 03-04-SUMMARY.md]
started: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Full test suite green
expected: Run `cd backend && python -m pytest tests/ -q`. All tests pass — 142 passed, 5 xfailed, 6 warnings, zero failures.
result: pass
notes: 147 passed, 0 failures (xfailed tests now pass — code review fixes resolved previously-expected failures)

### 2. chat_log branch exists in pipeline
expected: `_stage_parse_and_chunk` has a `chat_log` branch routing to `parse_text`. `grep -n "chat_log" backend/app/pipeline/pipeline.py` shows the branch.
result: pass
notes: Line 140-141 — `elif source.source_type == "chat_log" and source.raw_text:` routes to `parse_text`

### 3. ConceptSource idempotency — no duplicate rows on re-run
expected: Both `_create_new_concept` and `_merge_into_existing` check for existing `ConceptSource` before inserting. `grep -n "existing_cs" backend/app/pipeline/resolver.py` shows the check in both functions.
result: pass
notes: Lines 154, 160, 201, 207 — existence check in both functions

### 4. Session not held open across LLM tiebreaker call
expected: `_resolve_concept` uses multiple `async with AsyncSessionLocal` blocks, not one wrapping the LLM call.
result: pass
notes: 6 separate `async with AsyncSessionLocal` blocks in resolver.py — LLM call happens outside any open session

### 5. Batch cache lookup in _co_occurrence_edges
expected: Single batch `IN (...)` query replaces per-chunk sessions. `grep` shows `chunk_hash.in_` and `cache_map`.
result: pass
notes: Lines 99-113 — `chunk_hashes` list built upfront, single `IN (...)` query, `cache_map` dict used in loop

### 6. BFS depth bulk UPDATE
expected: `_compute_depths` uses `sa.case()` for a single bulk UPDATE instead of N individual statements.
result: pass
notes: Lines 319, 323 — `case_expr = sa.case(depths, value=Concept.id)` in single UPDATE

### 7. Embedding failure logged in resolver
expected: `resolver.py` has a logger and warning call near the embeddings call.
result: pass
notes: Lines 16, 28, 252 — `logging` imported, `_log` logger at module level, `_log.warning(...)` before re-raise

### 8. run_edges passes course_id to _co_occurrence_edges
expected: `_co_occurrence_edges` signature accepts `course_id` parameter; `run_edges` fetches it once and passes it.
result: pass
notes: Line 69 — `async def _co_occurrence_edges(source_id: int, course_id: int | None = None)`

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0

## Gaps

[none]
