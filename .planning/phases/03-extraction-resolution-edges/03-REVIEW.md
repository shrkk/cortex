---
phase: 03-extraction-resolution-edges
reviewed: 2026-04-25T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - backend/app/pipeline/edges.py
  - backend/app/pipeline/extractor.py
  - backend/app/pipeline/pipeline.py
  - backend/app/pipeline/resolver.py
  - backend/tests/test_edges.py
  - backend/tests/test_extraction.py
  - backend/tests/test_pipeline.py
  - backend/tests/test_resolution.py
findings:
  critical: 4
  warning: 6
  info: 3
  total: 13
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-04-25T00:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

The extraction, resolution, and edge inference pipeline stages are implemented. The core logic is structurally sound and the RESEARCH.md pitfalls (cross-course merging, cosine operator, embedding concatenation, BFS isolated fallback) are all addressed. However, four blockers were found: a silent data loss path for `chat_log` sources, a duplicate `ConceptSource` row bug on re-runs, a DB session held open across an LLM network call causing potential connection pool exhaustion, and a silent merge failure when `session.get()` returns `None`. Six additional warnings cover correctness and robustness issues.

---

## Critical Issues

### CR-01: `chat_log` source type produces zero chunks — entire pipeline silently no-ops

**File:** `backend/app/pipeline/pipeline.py:116-138`

**Issue:** `_stage_parse_and_chunk` handles `pdf`, `url`, `image`, and `text` source types, but has no branch for `chat_log`. When `source_type == "chat_log"`, `chunks_data` stays `[]`, no `Chunk` rows are created, and every downstream stage (`_stage_extract`, `_stage_resolve`, `_stage_edges`) hits the early-return guard (`if not chunks: return`). The source ends up `status=done` with zero extracted concepts, no edges, and no error. The `extractor.py` and `resolver.py` are both specifically coded to handle `chat_log` (questions extraction, `student_questions` wiring) — that dead code indicates `chat_log` was intended to be supported but the parser branch was never added.

**Fix:**
```python
elif source.source_type == "chat_log" and source.raw_text:
    # chat_log: treat raw_text as plain text; questions extracted in _stage_extract
    chunks_data, title = await parse_text(source.raw_text, source.title)
```
Add this branch after the `text` branch (line 137). Alternatively, add a parser alias so `chat_log` falls through to `parse_text`.

---

### CR-02: `_merge_into_existing` silently skips key_points/gotchas/examples update when `session.get()` returns `None`

**File:** `backend/app/pipeline/resolver.py:179-192`

**Issue:** `_merge_into_existing` calls `session.get(Concept, row.id)` to reload the concept into the ORM identity map. If the concept was inserted in an earlier call within the same pipeline run and subsequently expired (e.g., after a `commit()`), or if the identity-map entry is absent, `session.get()` can return `None`. When `existing is None` (line 180), the `if existing is not None:` block is skipped entirely — `key_points`, `gotchas`, and `examples` are not merged/updated. Execution falls through to the `ConceptSource` insert, which succeeds, so the merge appears to work but the concept's lists are never enriched. This is a silent data loss: new key points from additional sources are dropped without any error or log.

**Fix:**
```python
existing = await session.get(Concept, row.id)
if existing is None:
    # Concept was evicted from identity map — reload it
    existing = await session.scalar(
        sa.select(Concept).where(Concept.id == row.id)
    )
if existing is not None:
    existing.key_points = list(dict.fromkeys(
        (existing.key_points or []) + list(key_points or [])
    ))[:10]
    existing.gotchas = list(dict.fromkeys(
        (existing.gotchas or []) + list(gotchas or [])
    ))[:5]
    existing.examples = list(dict.fromkeys(
        (existing.examples or []) + list(examples or [])
    ))[:5]
else:
    raise RuntimeError(f"Concept {row.id} not found during merge")
```

---

### CR-03: DB session held open across LLM network call — connection pool exhaustion under load

**File:** `backend/app/pipeline/resolver.py:229-277`

**Issue:** In `_resolve_concept`, a single `async with AsyncSessionLocal() as session:` block spans lines 229–277. Inside this block, after the cosine query (line 229–246), the code may call `_llm_tiebreaker(...)` at line 262 — a network I/O call to the Anthropic API that typically takes 1–5 seconds. The DB session (and its underlying connection) is held open for the entire duration of that LLM call. Under any concurrent pipeline load, this will exhaust the async connection pool (typically 5–20 connections). If 5 resolvers are each waiting on a tiebreaker call, 5 connections are blocked, and all subsequent DB operations stall.

**Fix:** Close the session before the LLM call and reopen it afterward:
```python
async with AsyncSessionLocal() as session:
    cosine_result = await session.execute(...)
    row = cosine_result.first()

# Session is now closed — free the connection
if row is None or row.dist > _TIEBREAKER_MAX_DIST:
    async with AsyncSessionLocal() as session:
        return await _create_new_concept(session, ...)

if row.dist <= _AUTO_MERGE_DIST:
    async with AsyncSessionLocal() as session:
        return await _merge_into_existing(session, row, ...)

# Tiebreaker path — LLM call outside any session
decision = await _llm_tiebreaker(...)
async with AsyncSessionLocal() as session:
    if decision.get("same"):
        return await _merge_into_existing(session, row, ...)
    return await _create_new_concept(session, ...)
```

---

### CR-04: `ConceptSource` duplicate rows inserted on repeated pipeline runs

**File:** `backend/app/pipeline/resolver.py:185-189` and `backend/app/pipeline/resolver.py:150-157`

**Issue:** Both `_create_new_concept` and `_merge_into_existing` call `session.add(ConceptSource(concept_id=..., source_id=...))` unconditionally. There is no unique constraint on `(concept_id, source_id)` in the `ConceptSource` model or referenced in a migration. When the pipeline is re-run for the same `source_id` (e.g., after a transient error, or when `force=True`), every concept from that source gets a new `ConceptSource` row. This creates duplicate `ConceptSource` entries for the same `(concept_id, source_id)` pair, corrupting the source attribution data. The CLAUDE.md notes that the pipeline must be idempotent on re-runs.

**Fix:** Use an upsert (INSERT ... ON CONFLICT DO NOTHING) or check for existence first:
```python
# Option A — check before insert (simple):
existing_cs = await session.scalar(
    sa.select(ConceptSource).where(
        ConceptSource.concept_id == concept_id,
        ConceptSource.source_id == source_id,
    )
)
if existing_cs is None:
    session.add(ConceptSource(
        concept_id=concept_id,
        source_id=source_id,
        student_questions=...,
    ))

# Option B — add a UniqueConstraint to the model and use pg_insert ON CONFLICT DO NOTHING
```
The longer-term fix is a `UniqueConstraint("concept_id", "source_id")` on the `ConceptSource` table with an accompanying Alembic migration.

---

## Warnings

### WR-01: N+1 DB sessions inside `_co_occurrence_edges` cache-lookup loop

**File:** `backend/app/pipeline/edges.py:93-103`

**Issue:** The loop at line 93 opens a new `AsyncSessionLocal` session for every chunk to look up the `ExtractionCache` row. For a source with 100 chunks, this opens 100 DB connections sequentially. The pattern is unnecessary — a single session with a batch `WHERE chunk_hash IN (...)` query would replace the entire loop. Under connection pool pressure (e.g., multiple concurrent pipelines), this loop will block for pool acquisition on each iteration, significantly increasing latency and risking pool exhaustion.

**Fix:**
```python
chunk_hashes = [hashlib.sha256(t.encode("utf-8")).hexdigest() for _, t in chunk_rows]
async with AsyncSessionLocal() as session:
    cache_result = await session.execute(
        sa.select(ExtractionCache).where(
            ExtractionCache.chunk_hash.in_(chunk_hashes),
            ExtractionCache.model_version == MODEL_VERSION,
        )
    )
    cache_map = {r.chunk_hash: r for r in cache_result.scalars()}
```
Then use `cache_map.get(chunk_hash)` in the loop instead of per-chunk sessions.

---

### WR-02: `_compute_depths` bulk UPDATE issues N individual UPDATE statements — not atomic

**File:** `backend/app/pipeline/edges.py:304-309`

**Issue:** The loop at line 305-308 calls `await session.execute(sa.update(Concept).where(...).values(depth=...))` once per concept — N round-trips within a single transaction. With 500 concepts, this issues 500 SQL statements. More critically, if the loop is interrupted (e.g., connection reset between statements), some concepts get `depth` set and others do not, leaving the course in a partially-updated state. Since the session's `commit()` is called only at line 309, an interruption after some updates but before commit leaves all changes un-committed (which is actually safe due to rollback-on-close). However, the N-roundtrip pattern inside a single transaction is fragile and not atomic in the way the code implies.

The actual bug: `sa.update(Concept).where(Concept.id == cid).values(depth=depth)` does not load the ORM object — it issues a bulk UPDATE. But inside the same session, ORM-cached `Concept` objects are NOT refreshed. If `_prerequisite_edges` or any subsequent reader uses the same session (they don't here), stale depth values could be read. This is safe given the current session-per-stage pattern but documents a subtle invariant.

**Fix:** Use a single bulk UPDATE with CASE WHEN or a temporary table, or at minimum document that depths are committed atomically:
```python
# Replace the loop with a single case-expression update
from sqlalchemy import case
depth_map_cases = [(cid, depth) for cid, depth in depths.items()]
case_expr = case(
    {cid: depth for cid, depth in depths.items()},
    value=Concept.id,
)
await session.execute(
    sa.update(Concept)
    .where(Concept.id.in_(depths.keys()))
    .values(depth=case_expr)
)
await session.commit()
```

---

### WR-03: `_co_occurrence_edges` SELECT-then-UPDATE is not race-condition safe

**File:** `backend/app/pipeline/edges.py:136-153`

**Issue:** The SELECT-then-UPDATE pattern for co-occurrence edges (lines 136-153) is not protected by `SELECT ... FOR UPDATE` or any other row-level lock. If two pipeline workers process different sources in the same course concurrently, both workers can SELECT the same edge row, see `existing is None`, and both INSERT a new edge for the same `(from_id, to_id, co_occurrence)` pair. The docstring acknowledges "no unique index on edges (from_id,to_id,edge_type)" but does not address the race condition — the SELECT-then-UPDATE design only prevents duplicates when runs are truly sequential.

**Fix:** Add `FOR UPDATE` to the SELECT to serialize concurrent access:
```python
existing = await session.scalar(
    sa.select(Edge)
    .where(
        Edge.from_id == a,
        Edge.to_id == b,
        Edge.edge_type == "co_occurrence",
    )
    .with_for_update()
)
```
Or, alternatively, insert a `UniqueConstraint` on `(from_id, to_id, edge_type)` for co-occurrence edges and use an upsert (`INSERT ... ON CONFLICT DO UPDATE SET weight = weight + 1`), which is atomic and correct.

---

### WR-04: `_extract_one` chat_log questions overwrite prior questions on cache hit

**File:** `backend/app/pipeline/extractor.py:218-248`

**Issue:** When `source_type == "chat_log"` and the chunk has a cache hit from a prior run (the `_extract_chunk_with_cache` call returns early at line 128), the code at line 228 still re-reads the cache and then at line 234-239 rebuilds `wrapped` including new `_questions`. If the cache row already contains a `dict` payload with `_questions`, the new `_questions` list **replaces** the existing one entirely (`wrapped["_questions"] = questions` at line 237). If a prior run processed the same chunk with a different set of questions extracted (e.g., slightly different text normalization), the previous questions are lost with no merge.

**Fix:** Merge rather than replace:
```python
elif isinstance(payload, dict):
    wrapped = dict(payload)
    existing_qs = wrapped.get("_questions") or []
    # Merge, deduplicate, preserve order
    merged = list(dict.fromkeys(existing_qs + questions))
    wrapped["_questions"] = merged
```

---

### WR-05: `_resolve_concept` does not handle OpenAI embedding failure — raises unhandled exception

**File:** `backend/app/pipeline/resolver.py:221-225`

**Issue:** The `openai_client.embeddings.create()` call at line 221 is not wrapped in a try/except. If the OpenAI API returns an error (rate limit, timeout, invalid key), the exception propagates up to `run_resolution`'s `except Exception: continue` at line 357 — which silently swallows it. This is actually safe at the per-concept level, but the `run_resolution` loop continues to the next concept without logging the failure. More importantly, in `_stage_embed` (pipeline.py line 187) embedding failures return early, preserving pipeline integrity. The pattern is inconsistent: embed failures in stage 3 are best-effort; embed failures in stage 5 are silently swallowed per-concept. A transient OpenAI outage during resolution will leave all concepts for a chunk unresolved with no diagnostic information.

**Fix:** Log the embedding failure before continuing:
```python
try:
    embed_resp = await openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=[embed_input],
    )
    vec = embed_resp.data[0].embedding
except Exception as exc:
    # Log the failure — caller's except will swallow it, losing diagnostic info
    import logging
    logging.getLogger(__name__).warning(
        "Embedding failed for concept '%s': %s", title, exc
    )
    raise  # re-raise so caller's except block handles it
```

---

### WR-06: `run_edges` fetches `Source` redundantly — second read can race with `_co_occurrence_edges`

**File:** `backend/app/pipeline/edges.py:323-332`

**Issue:** `run_edges` fetches `Source.course_id` at lines 324-328 to pass to `_prerequisite_edges` and `_compute_depths`. But `_co_occurrence_edges` also fetches `Source` independently at lines 77-81 and extracts `course_id` from it. If the `Source` row is deleted between these two reads (unlikely but possible), `run_edges` has a valid `course_id` while `_co_occurrence_edges` returns early — resulting in `_prerequisite_edges` and `_compute_depths` running against a course whose source was deleted mid-pipeline. The redundant fetch also means two DB round-trips where one suffices.

**Fix:** Fetch `course_id` once in `run_edges` and pass it to all three sub-functions:
```python
async def run_edges(source_id: int) -> None:
    async with AsyncSessionLocal() as session:
        src_row = await session.scalar(sa.select(Source).where(Source.id == source_id))
        if src_row is None:
            return
        course_id: int = src_row.course_id

    await _co_occurrence_edges(source_id, course_id)   # pass course_id
    await _prerequisite_edges(course_id)
    await _compute_depths(course_id)
```
Update `_co_occurrence_edges` signature to accept `course_id` as a parameter and remove its internal `Source` fetch.

---

## Info

### IN-01: `_compute_depths` row-unpacking pattern has a dead/incorrect else-branch

**File:** `backend/app/pipeline/edges.py:260`

**Issue:** The set comprehension `{r[0] if isinstance(r, tuple) else r for r in result}` has an else-branch that falls back to `r` itself. `session.execute(sa.select(Concept.id)...)` always returns `Row` tuples with a single column — `r[0]` is always the correct path. If `r` were somehow not a tuple (e.g., a mapped ORM object), `r` would not be an `int` and the set would contain non-int objects, silently breaking the BFS. The else-branch is dead code that gives false reassurance.

**Fix:** Use explicit scalar-column extraction:
```python
result = await session.execute(
    sa.select(Concept.id).where(Concept.course_id == course_id)
)
concept_ids: set[int] = set(result.scalars())
```

---

### IN-02: `test_run_edges_calls_all_three_substages` session mock is not actually exercised

**File:** `backend/tests/test_edges.py:214-238`

**Issue:** The test patches `_co_occurrence_edges`, `_prerequisite_edges`, and `_compute_depths` with `AsyncMock`, so those functions never run. The test also sets up a complex session mock (lines 224-232) for the `Source` lookup in `run_edges`. However, `run_edges` calls `session.scalar(...)` directly, while the mock sets up `result.scalar_one` — these are different method paths. The `session.scalar` call returns an `AsyncMock` (truthy), so `src_row is None` is never True and the early return is never triggered. The test passes but does not verify that `run_edges` correctly reads `course_id` from the source — a regression where `run_edges` used a hardcoded `course_id=0` would still pass this test.

**Fix:** Assert that `_prerequisite_edges` and `_compute_depths` were called with the correct `course_id`:
```python
pq.assert_awaited_once_with(42)
cd.assert_awaited_once_with(42)
```
And fix the session mock to make `session.scalar` return the `src_row` mock directly.

---

### IN-03: Bare `except Exception` blocks swallow all errors without logging

**File:** `backend/app/pipeline/edges.py:214`, `backend/app/pipeline/resolver.py:357`, `backend/app/pipeline/extractor.py:160`

**Issue:** Multiple `except Exception: continue` or `except Exception: pass` blocks (with `# noqa: BLE001`) silently discard all failures, including transient network errors, SDK changes, and programming mistakes. While the BLE001 suppression is intentional, there is no logging — failures during extraction, resolution, or prerequisite edge inference are invisible in production. A concept that consistently fails to extract will silently produce zero output indefinitely with no trace in logs or the `source.error` column.

**Fix:** Add structured logging at WARNING level before the continue/pass:
```python
import logging
_log = logging.getLogger(__name__)

except Exception as exc:  # noqa: BLE001
    _log.warning("Concept extraction failed for chunk %s: %r", chunk.id, exc)
    continue
```

---

_Reviewed: 2026-04-25T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
