---
phase: 3
slug: extraction-resolution-edges
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-25
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (asyncio) |
| **Config file** | `backend/pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` |
| **Quick run command** | `cd backend && pytest tests/test_extraction.py -x -q` |
| **Full suite command** | `cd backend && pytest tests/ -x -q` |
| **Estimated runtime** | ~15–30 seconds (mocked LLM calls) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/test_extraction.py -x -q`
- **After every plan wave:** Run `cd backend && pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 0 | EXTRACT-01 | — | N/A | unit | `pytest tests/test_extraction.py::test_extract_stub -x -q` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 0 | EXTRACT-04 | — | Strict schema prevents injection | unit | `pytest tests/test_extraction.py::test_tool_use_schema -x -q` | ❌ W0 | ⬜ pending |
| 3-01-03 | 01 | 0 | EXTRACT-05 | — | N/A | unit | `pytest tests/test_extraction.py::test_cache_hit -x -q` | ❌ W0 | ⬜ pending |
| 3-01-04 | 01 | 1 | EXTRACT-01 | — | N/A | integration | `pytest tests/test_extraction.py::test_extract_concepts -x -q` | ✅ | ⬜ pending |
| 3-01-05 | 01 | 1 | EXTRACT-02 | — | N/A | unit | `pytest tests/test_extraction.py::test_concept_fields -x -q` | ✅ | ⬜ pending |
| 3-01-06 | 01 | 1 | EXTRACT-03 | — | N/A | unit | `pytest tests/test_extraction.py::test_chat_log_questions -x -q` | ✅ | ⬜ pending |
| 3-01-07 | 01 | 1 | EXTRACT-05 | — | N/A | unit | `pytest tests/test_extraction.py::test_parallel_semaphore -x -q` | ✅ | ⬜ pending |
| 3-02-01 | 02 | 0 | RESOLVE-01 | — | Course-scoped only | unit | `pytest tests/test_resolution.py::test_resolve_stub -x -q` | ❌ W0 | ⬜ pending |
| 3-02-02 | 02 | 1 | RESOLVE-02 | — | N/A | unit | `pytest tests/test_resolution.py::test_high_cosine_merge -x -q` | ✅ | ⬜ pending |
| 3-02-03 | 02 | 1 | RESOLVE-03 | — | N/A | unit | `pytest tests/test_resolution.py::test_tiebreaker -x -q` | ✅ | ⬜ pending |
| 3-02-04 | 02 | 1 | RESOLVE-04 | — | N/A | unit | `pytest tests/test_resolution.py::test_low_cosine_new -x -q` | ✅ | ⬜ pending |
| 3-02-05 | 02 | 1 | RESOLVE-01 | T-3-01 | course_id filter always present | unit | `pytest tests/test_resolution.py::test_course_scoped -x -q` | ✅ | ⬜ pending |
| 3-02-06 | 02 | 1 | RESOLVE-05 | — | N/A | integration | `pytest tests/test_resolution.py::test_dedup_same_course -x -q` | ✅ | ⬜ pending |
| 3-03-01 | 03 | 0 | EDGE-01 | — | N/A | unit | `pytest tests/test_edges.py::test_edges_stub -x -q` | ❌ W0 | ⬜ pending |
| 3-03-02 | 03 | 1 | EDGE-01 | — | N/A | unit | `pytest tests/test_edges.py::test_contains_implicit -x -q` | ✅ | ⬜ pending |
| 3-03-03 | 03 | 1 | EDGE-02 | — | N/A | unit | `pytest tests/test_edges.py::test_cooccurrence -x -q` | ✅ | ⬜ pending |
| 3-03-04 | 03 | 1 | EDGE-03 | — | N/A | unit | `pytest tests/test_edges.py::test_prerequisite_inference -x -q` | ✅ | ⬜ pending |
| 3-03-05 | 03 | 1 | EDGE-04 | — | N/A | unit | `pytest tests/test_edges.py::test_bfs_depth -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_extraction.py` — RED stubs for EXTRACT-01 through EXTRACT-05
- [ ] `backend/tests/test_resolution.py` — RED stubs for RESOLVE-01 through RESOLVE-05
- [ ] `backend/tests/test_edges.py` — RED stubs for EDGE-01 through EDGE-04
- [ ] Mock fixtures for `anthropic.AsyncAnthropic` in `conftest.py` (existing infrastructure may need extension)

*Existing test infrastructure (`conftest.py`, `pytest-asyncio`) already in place from Phases 1-2.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CS229 PDF produces 10–40 specific concepts | EXTRACT-01 | Requires live Claude API + real PDF; quality is subjective | `TRUNCATE extraction_cache; POST /ingest with cs229 PDF; SELECT count(*), title FROM concepts WHERE course_id=X GROUP BY title;` |
| Two PDFs on "Gradient Descent" → ONE concept node | RESOLVE-05 | Requires live embeddings + real content | Drop same-topic PDFs twice; `SELECT id, title FROM concepts WHERE course_id=X AND title ILIKE '%gradient%';` |
| BFS depth is non-null for all concepts | EDGE-04 | Requires end-to-end pipeline run | `SELECT count(*) FROM concepts WHERE course_id=X AND depth IS NULL; -- expect 0` |
| Extraction cache skips LLM on second run | EXTRACT-05 | Requires checking logs for cache-hit messages | Run pipeline twice on same source; `SELECT count(*) FROM extraction_cache;` — count should not double |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (test_extraction.py, test_resolution.py, test_edges.py)
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** 2026-04-25
