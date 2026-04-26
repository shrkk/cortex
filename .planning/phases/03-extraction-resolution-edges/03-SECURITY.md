---
phase: 03-extraction-resolution-edges
audited: 2026-04-25
asvs_level: L1
threats_total: 21
threats_closed: 21
threats_open: 0
---

# Phase 03: Security Audit

## Threat Register

| ID | Category | Component | Disposition | Status | Evidence |
|----|----------|-----------|-------------|--------|----------|
| T-3-02-01 | Tampering | extractor.py — EXTRACT_TOOL schema + tool_choice | mitigate | CLOSED | `additionalProperties: False` at schema root (line 45) and items level (line 53); `tool_choice={"type":"tool","name":"extract_concepts"}` (line 138); `chunk.text[:8000]` truncation (line 145) |
| T-3-02-02 | Information Disclosure | extractor.py — API key handling | mitigate | CLOSED | Key loaded only via `settings.anthropic_api_key` (line 209); no logging calls in extractor.py; `except Exception: concepts = []` at line 160 discards SDK exceptions without propagating traceback |
| T-3-02-03 | Denial of Service | extractor.py — oversized output | mitigate | CLOSED | `maxItems: 6` on EXTRACT_TOOL concepts array (line 50); `[:8000]` per-chunk truncation (line 145); `asyncio.Semaphore(5)` (line 211); cache lookup at lines 120-128 prevents repeat token spend |
| T-3-02-04 | Denial of Service | extractor.py — rate limit handling | mitigate | CLOSED | `for attempt in range(2)` retry loop (lines 132-162); `except Exception: concepts = []` fallback (lines 160-161); cache UPSERT at lines 165-175 always writes (even empty list) |
| T-3-02-05 | Repudiation | extractor.py — cache key collision | accept | CLOSED | Accepted risk — see Accepted Risks table |
| T-3-02-06 | Tampering | extractor.py — unicode encoding | mitigate | CLOSED | `chunk.text.encode("utf-8")` before sha256 (line 117); also line 221 in chat_log branch |
| T-3-03-01 | Tampering | resolver.py — cross-course merge | mitigate | CLOSED | `Concept.course_id == course_id` WHERE clause in cosine query (line 270), annotated "RESOLVE-01 — NEVER omit" |
| T-3-03-02 | Tampering | resolver.py — tiebreaker prompt injection | mitigate | CLOSED | TIEBREAKER_TOOL has `additionalProperties: False` (line 42), `required: ["same", "reason"]` (line 43); output parsed via `tool_block.input` dict (line 114) |
| T-3-03-03 | Information Disclosure | resolver.py — cosine query scope | mitigate | CLOSED | `Concept.course_id == course_id` in cosine SELECT (line 270) scopes results to target course |
| T-3-03-04 | Denial of Service | resolver.py — unbounded JSON list growth | mitigate | CLOSED | `dict.fromkeys(...)[:10]` on key_points (line 196); `[:5]` on gotchas (line 197); `[:5]` on examples (line 198); `dict.fromkeys` dedup on all three |
| T-3-03-05 | Denial of Service | resolver.py — embedding rate limit | accept | CLOSED | Accepted risk — see Accepted Risks table |
| T-3-03-06 | Repudiation | resolver.py — tiebreaker non-determinism | accept | CLOSED | Accepted risk — see Accepted Risks table |
| T-3-03-07 | Tampering | resolver.py — cache payload schema drift | mitigate | CLOSED | `isinstance(payload, dict)` branch at lines 365-370 normalizes both payload shapes; `from app.pipeline.extractor import MODEL_VERSION` at line 27 |
| T-3-04-01 | Tampering | edges.py — hallucinated concept titles | mitigate | CLOSED | `if t in title_to_id` guard at line 143 before dict access; titles not present in the course-scoped lookup map are silently dropped |
| T-3-04-02 | Tampering | edges.py — wrong-course concept in edge | mitigate | CLOSED | `Concept.course_id == course_id` WHERE in title_to_id batch query (lines 133-135) |
| T-3-04-03 | Denial of Service | edges.py — cyclic graph BFS | mitigate | CLOSED | `if child_id not in depths` guard at line 308; visited nodes never re-enqueued; isolated/cyclic fallback assigns depth=1 (lines 313-315) |
| T-3-04-04 | Denial of Service | edges.py — large course LLM/DB | mitigate | CLOSED | `BATCH_SIZE = 50` (line 201); `maxItems: 30` on PREREQ_TOOL output schema (line 46); BFS is O(V+E) |
| T-3-04-05 | Repudiation | edges.py — duplicate edge rows on re-run | mitigate | CLOSED | Co-occurrence: SELECT-then-UPDATE at lines 149-167 increments weight on existing edge; prerequisite: existence check at lines 243-250, only inserts if `existing is None` |
| T-3-04-06 | Information Disclosure | edges.py — course title in LLM prompt | accept | CLOSED | Accepted risk — see Accepted Risks table |
| T-3-04-07 | Tampering | pipeline.py — Phase 4 stubs preserved | mitigate | CLOSED | `_stage_flashcards_stub` defined (line 233) and called (line 38); `_stage_signals_stub` defined (line 239) and called (line 39) |
| T-3-04-08 | Denial of Service | edges.py — sequential depth UPDATEs | accept | CLOSED | Accepted risk (noted as now mitigated via bulk CASE-WHEN) — see Accepted Risks table |

## Accepted Risks

| ID | Rationale |
|----|-----------|
| T-3-02-05 | sha256 collision probability is negligible (~2^-128 under birthday bound for practical dataset sizes). No additional mitigation warranted for v1. |
| T-3-03-05 | Concept resolution is sequential per-chunk by design to avoid race conditions on cosine queries within the same course. This bounds throughput but prevents incorrect canonical ID assignment. Accepted for v1; rate-limit retries deferred to a later phase. |
| T-3-03-06 | LLM tiebreaker output is inherently non-deterministic. The conservative fallback (`same: False`) minimizes incorrect merges. Human review recommended for ambiguous cases. |
| T-3-04-06 | Course title is not sensitive PII or secret data; it is required for the prerequisite inference prompt to produce correct course-scoped relationships. Risk accepted. |
| T-3-04-08 | Originally accepted as negligible for v1 (<=40 concepts). Subsequently mitigated ahead of schedule: _compute_depths now uses a single bulk CASE-WHEN UPDATE (edges.py lines 318-325). Documented as closed-by-implementation. |

## Audit Trail

### 2026-04-25

| Metric | Count |
|--------|-------|
| Threats found | 21 |
| Closed | 21 |
| Open | 0 |
| Blockers | 0 |
| Unregistered flags | 0 |

**Auditor notes:**

- All 16 `mitigate` dispositions verified against source code with line-level evidence.
- All 5 `accept` dispositions documented above; no acceptance entry was missing.
- T-3-04-07: `_stage_flashcards_stub` and `_stage_signals_stub` are present and wired into `run_pipeline`. They now delegate to real Phase 4 implementations (`run_flashcards`, `run_signals`) rather than being no-ops, but the stub wrappers remain in pipeline.py as required.
- T-3-04-08: Mitigation described in threat register as "now actually mitigated" is confirmed in code — bulk CASE-WHEN UPDATE via `sa.case(depths, value=Concept.id)` at edges.py line 319.
- No new unregistered attack surface was identified during code review (per adversarial constraint: this audit verifies declared threats only, does not scan for new vulnerabilities).
