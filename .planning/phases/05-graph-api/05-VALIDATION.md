---
phase: 5
slug: graph-api
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-25
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `backend/pytest.ini` or `backend/pyproject.toml` |
| **Quick run command** | `cd backend && pytest tests/test_graph_api.py -x -q` |
| **Full suite command** | `cd backend && pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && pytest tests/test_graph_api.py -x -q`
- **After every plan wave:** Run `cd backend && pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 0 | GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-05, GRAPH-06, GRAPH-07 | T-5-01 / — | Courses only returned for user_id=1; graph validates course ownership | unit (RED) | `cd backend && pytest tests/test_graph_api.py -x -q` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 0 | GRAPH-04 | T-5-03 / — | Concept detail validates concept belongs to requested course | unit (RED) | `cd backend && pytest tests/test_concept_detail.py -x -q` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 1 | GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-05, GRAPH-06, GRAPH-07 | T-5-01, T-5-02 / — | Graph returns only nodes for requested course_id | integration | `cd backend && pytest tests/test_graph_api.py -x -q` | ✅ W0 | ⬜ pending |
| 05-03-01 | 03 | 1 | GRAPH-04 | T-5-03 / — | definition→summary field mapped correctly | integration | `cd backend && pytest tests/test_concept_detail.py -x -q` | ✅ W0 | ⬜ pending |
| 05-03-02 | 03 | 1 | GRAPH-04 | — | concepts router registered at /concepts prefix | integration | `cd backend && pytest tests/test_concept_detail.py -x -q` | ✅ W0 | ⬜ pending |
| 05-04-01 | 04 | 2 | GRAPH-01–07 | — | Full suite green | integration | `cd backend && pytest tests/ -x -q` | ✅ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_graph_api.py` — stubs for GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-05, GRAPH-06, GRAPH-07 (GET /courses, POST /courses, GET /courses/{id}/graph, GET /courses/match)
- [ ] `backend/tests/test_concept_detail.py` — stubs for GRAPH-04 (GET /concepts/{id})
- [ ] `backend/tests/conftest.py` — shared DB fixtures (if not already present)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Graph response time < 200ms for a course with 20+ concepts | GRAPH-06 (polling) | Requires seeded data with realistic scale | Seed demo data, `time curl http://localhost:8000/courses/1/graph`, verify < 200ms |
| `curl \| jq` produces readable node/edge structure | GRAPH-03 success criteria | Structural format check | `curl http://localhost:8000/courses/1/graph \| jq '.nodes[] \| .type'` shows course/concept/flashcard/quiz |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
