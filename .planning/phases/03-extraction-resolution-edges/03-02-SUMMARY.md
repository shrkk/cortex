---
phase: 03-extraction-resolution-edges
plan: "02"
subsystem: backend-pipeline
tags:
  - phase-03
  - llm
  - extraction
  - cache

dependency_graph:
  requires:
    - 03-01  # Wave 0 stub + test_extraction.py RED suite
  provides:
    - extractor.py fully implemented
    - ExtractionCache upsert pattern
    - Cache payload contract for resolver (Plan 03-03)
  affects:
    - backend/app/pipeline/extractor.py

tech_stack:
  added: []
  patterns:
    - "Claude tool_use with tool_choice forcing (type=tool, name=extract_concepts)"
    - "asyncio.Semaphore(5) for max-5 parallel chunk extractions"
    - "pg_insert.on_conflict_do_update for upsert on (chunk_hash, model_version)"
    - "sha256 hex digest as cache key (UTF-8 explicit encoding)"
    - "Retry-once loop (range(2)) on stop_reason != tool_use"

key_files:
  created: []
  modified:
    - backend/app/pipeline/extractor.py

decisions:
  - "Cache payload contract: default=list[dict]; chat_log=dict{concepts,_questions} — resolver normalizes both shapes"
  - "LLM retry implemented as range(2) loop at single call site (call_count==2 verifiable by mock)"
  - "Chat_log questions stored as _questions key in ExtractionCache extracted_concepts dict after initial extraction"
  - "Settings API key guard (if not settings.anthropic_api_key: return) matches _stage_embed pattern"

metrics:
  duration: "~18 minutes"
  completed: "2026-04-26"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 1
---

# Phase 03 Plan 02: Extractor Implementation Summary

**One-liner:** Full Claude tool_use concept extraction with SHA-256 cache lookup, forced tool_choice, retry-on-end_turn, and asyncio.Semaphore(5) parallel processing.

## Test Counts: RED -> GREEN Transition

| Test file | Before (Wave 0) | After (Wave 1) |
|-----------|-----------------|----------------|
| tests/test_extraction.py | 0 passed / 13 failed | 13 passed / 0 failed |
| Full suite (excl. test_resolution.py, test_edges.py) | 67 passed | 80 passed |

The RED -> GREEN transition covers EXTRACT-01 through EXTRACT-05:
- **EXTRACT-01:** 0–6 concepts returned from tool_use response
- **EXTRACT-02:** All 6 required fields present per concept dict
- **EXTRACT-03:** `_extract_questions` regex extracts verbatim questions; chat_log cache payload wraps as `{"concepts": [...], "_questions": [...]}`
- **EXTRACT-04:** `tool_choice={"type": "tool", "name": "extract_concepts"}` forces tool use; retry once on `stop_reason == "end_turn"` (exactly 2 LLM calls on double failure)
- **EXTRACT-05:** ExtractionCache lookup skips LLM entirely on hit; asyncio.Semaphore(5) caps concurrency; SHA-256 of `chunk.text.encode("utf-8")` as cache key

## Cache Payload Contract (for Plan 03-03 Resolver)

The `extraction_cache.extracted_concepts` column (JSON) holds one of two shapes:

```
# Default (pdf, url, image, text sources):
list[dict]  # list of concept dicts with 6 required fields

# chat_log sources only (after run_extraction augmentation):
{
  "concepts": list[dict],   # same concept dicts
  "_questions": list[str]   # verbatim student questions ending in "?"
}
```

**Resolver normalization (Plan 03-03 must implement):**
```python
payload = cached.extracted_concepts
concepts = payload if isinstance(payload, list) else payload.get("concepts", [])
questions = [] if isinstance(payload, list) else payload.get("_questions", [])
```

## Anthropic API Call Patterns Established

- **Model:** `claude-sonnet-4-6` (from `parsers.py` pattern; matches PROJECT.md constraint)
- **max_tokens:** 4096
- **tool_choice:** `{"type": "tool", "name": "extract_concepts"}` — forces tool use every time
- **Input truncation:** `chunk.text[:8000]` — prevents oversized prompt (T-3-02-01 mitigation)
- **Single call site:** one `await anthropic_client.messages.create(...)` inside `range(2)` loop
- **MODEL_VERSION:** `"claude-sonnet-4-6:v1"` — bump `:vN` to invalidate cache on schema changes

## Performance Notes

- **Semaphore(5):** Chosen per RESEARCH.md Pattern 3 — balances throughput vs. Anthropic rate limits. Can drop to 3 if pool exhaustion observed under load.
- **Cache-first:** Every chunk lookup hits ExtractionCache before any LLM call — prevents re-spend on repeated pipeline runs.
- **Session-per-operation:** Two separate `async with AsyncSessionLocal()` blocks in `_extract_chunk_with_cache` (one read, one write) — follows session-per-stage pattern from `pipeline.py`. Never passes session across boundaries.

## Pitfalls Encountered During Implementation

None — the plan's action block provided exact implementation code. Tests passed on first attempt.

One pre-existing environmental issue resolved: the worktree lacked a `.env` file (the main repo's `.env` was not copied to the worktree). Fixed by copying `backend/.env` to the worktree — this is a worktree setup prerequisite for all test runs.

## Deviations from Plan

None — plan executed exactly as written. The implementation in `extractor.py` exactly follows the pseudocode provided in Task 1 and Task 2 action blocks.

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundaries introduced. Security mitigations from threat model are implemented:
- T-3-02-01: `additionalProperties: False` on EXTRACT_TOOL schema, `tool_choice` forcing, `chunk.text[:8000]` truncation
- T-3-02-02: API key loaded only via `settings.anthropic_api_key`; exceptions caught in retry loop without re-raising key-containing context
- T-3-02-03: `maxItems: 6` on EXTRACT_TOOL schema, 8000-char truncation, `Semaphore(5)` cap, cache prevents re-spend
- T-3-02-06: `chunk.text.encode("utf-8")` explicit encoding before SHA-256

## Self-Check: PASSED

- [x] `backend/app/pipeline/extractor.py` exists (255 lines, > 200 minimum)
- [x] Commit `ee6db14` exists
- [x] All 13 `tests/test_extraction.py` tests pass
- [x] Full suite (80 tests) passes excluding intentionally RED files
- [x] `tool_choice`, `Semaphore(5)`, `hashlib.sha256`, `on_conflict_do_update` all present in source
