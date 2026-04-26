---
phase: 03-extraction-resolution-edges
fixed_at: 2026-04-25T00:00:00Z
review_path: .planning/phases/03-extraction-resolution-edges/03-REVIEW.md
iteration: 1
fix_scope: critical_warning
findings_in_scope: 10
fixed: 10
skipped: 0
status: all_fixed
---

# Phase 03: Code Review Fix Report

**Fixed at:** 2026-04-25T00:00:00Z
**Source review:** `.planning/phases/03-extraction-resolution-edges/03-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 10
- Fixed: 10
- Skipped: 0

## Fixed Issues

### CR-01: `chat_log` source type produces zero chunks — entire pipeline silently no-ops

**Files modified:** `backend/app/pipeline/pipeline.py`
**Commit:** 39b561f
**Applied fix:** Added an `elif source.source_type == "chat_log" and source.raw_text:` branch after the `text` branch in `_stage_parse_and_chunk`, delegating to `parse_text(source.raw_text, source.title)`. This routes `chat_log` sources through the same text parser, enabling downstream stages (extract, resolve, edges) to operate on the generated chunks.

---

### CR-02: `_merge_into_existing` silently skips key_points/gotchas/examples update when `session.get()` returns `None`

**Files modified:** `backend/app/pipeline/resolver.py`
**Commit:** a65b470
**Applied fix:** After `session.get(Concept, row.id)` returns `None`, added a fallback `session.scalar(sa.select(Concept).where(Concept.id == row.id))` to reload the concept from the database. If the reload also returns `None`, raises `RuntimeError(f"Concept {row.id} not found during merge")` instead of silently skipping the merge. This ensures `key_points`, `gotchas`, and `examples` are always enriched on the merge path.

---

### CR-03: DB session held open across LLM network call — connection pool exhaustion under load

**Files modified:** `backend/app/pipeline/resolver.py`
**Commit:** 1860ac8
**Applied fix:** Restructured `_resolve_concept` to close the cosine query session before any branching. Each disposition path (create new, auto-merge, tiebreaker+create, tiebreaker+merge) now opens its own fresh `AsyncSessionLocal` session. The `_llm_tiebreaker()` call happens entirely outside any open DB session. A comment was added to document the intent.

---

### CR-04: `ConceptSource` duplicate rows inserted on repeated pipeline runs

**Files modified:** `backend/app/pipeline/resolver.py`
**Commit:** 07593ee
**Applied fix:** Added a `session.scalar(sa.select(ConceptSource).where(...))` existence check before `session.add(ConceptSource(...))` in both `_create_new_concept` and `_merge_into_existing`. The insert is skipped when a `(concept_id, source_id)` row already exists, making both functions idempotent on re-runs.

---

### WR-01: N+1 DB sessions inside `_co_occurrence_edges` cache-lookup loop

**Files modified:** `backend/app/pipeline/edges.py`
**Commit:** 0e39b78
**Applied fix:** Replaced the per-chunk `AsyncSessionLocal` loop with a single batch query using `ExtractionCache.chunk_hash.in_(chunk_hashes)`. Built a `chunk_hash_to_id` mapping upfront, then a `cache_map` dict from the single query. The subsequent loop uses `cache_map.get(chunk_hash)` to look up cached payloads without any additional DB calls.

---

### WR-02: `_compute_depths` bulk UPDATE issues N individual UPDATE statements — not atomic

**Files modified:** `backend/app/pipeline/edges.py`
**Commit:** de77496
**Applied fix:** Replaced the per-concept UPDATE loop with a single `sa.case(depths, value=Concept.id)` expression used in a single `sa.update(Concept).where(Concept.id.in_(depths.keys())).values(depth=case_expr)` statement. All depths are now written in one SQL round-trip.

---

### WR-03: `_co_occurrence_edges` SELECT-then-UPDATE is not race-condition safe

**Files modified:** `backend/app/pipeline/edges.py`
**Commit:** aa962bd
**Applied fix:** Added `.with_for_update()` to the `sa.select(Edge)` query in the co-occurrence loop. Concurrent workers that attempt to SELECT the same edge row will now serialize, preventing duplicate INSERT for the same `(from_id, to_id, co_occurrence)` pair.

---

### WR-04: `_extract_one` chat_log questions overwrite prior questions on cache hit

**Files modified:** `backend/app/pipeline/extractor.py`
**Commit:** d3042e0
**Applied fix:** In the `elif isinstance(payload, dict):` branch, read `existing_qs = wrapped.get("_questions") or []` and replace the direct assignment with `wrapped["_questions"] = list(dict.fromkeys(existing_qs + questions))`. Prior questions are now merged and deduplicated in insertion order rather than overwritten.

---

### WR-05: `_resolve_concept` does not handle OpenAI embedding failure — raises unhandled exception

**Files modified:** `backend/app/pipeline/resolver.py`
**Commit:** f727724
**Applied fix:** Added `import logging` and `_log = logging.getLogger(__name__)` at module level. Wrapped `openai_client.embeddings.create()` in a `try/except Exception as exc` block that logs `_log.warning("Embedding failed for concept '%s': %s", title, exc)` before re-raising. The caller's `except Exception: continue` still handles per-concept failures, but failures are now visible in logs.

---

### WR-06: `run_edges` fetches `Source` redundantly

**Files modified:** `backend/app/pipeline/edges.py`
**Commit:** ece5764
**Applied fix:** Changed `_co_occurrence_edges` signature to `(source_id: int, course_id: int | None = None)`. When `course_id` is provided, the internal `Source` fetch is skipped. Updated `run_edges` to pass `course_id` to `_co_occurrence_edges(source_id, course_id)`. The `Source` row is now fetched exactly once per pipeline run of `run_edges`.

---

## Skipped Issues

None — all 10 in-scope findings were fixed.

---

_Fixed: 2026-04-25T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
