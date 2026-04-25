---
phase: 1
slug: infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-25
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| **Config file** | `backend/pytest.ini` (Wave 0 gap — create) |
| **Quick run command** | `pytest backend/tests/test_health.py -x` |
| **Full suite command** | `pytest backend/tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/tests/test_health.py -x`
- **After every plan wave:** Run `pytest backend/tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | INFRA-01 | — | N/A | smoke | `docker compose ps \| grep healthy` | ❌ Wave 0 | ⬜ pending |
| 1-01-02 | 01 | 0 | INFRA-02 | — | N/A | integration | `pytest tests/test_health.py::test_health_returns_ok -x` | ❌ Wave 0 | ⬜ pending |
| 1-01-03 | 01 | 0 | INFRA-03 | — | N/A | integration | `pytest tests/test_migration.py::test_all_tables_exist -x` | ❌ Wave 0 | ⬜ pending |
| 1-01-04 | 01 | 0 | INFRA-04 | — | N/A | integration | `pytest tests/test_seed.py::test_seed_creates_user_and_courses -x` | ❌ Wave 0 | ⬜ pending |
| 1-01-05 | 01 | 1 | INFRA-05 | — | No real secrets in .env.example | smoke | manual review | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/pytest.ini` — pytest config with `asyncio_mode = auto`
- [ ] `backend/tests/__init__.py` — empty init
- [ ] `backend/tests/conftest.py` — async test DB session fixtures
- [ ] `backend/tests/test_health.py` — covers INFRA-02
- [ ] `backend/tests/test_migration.py` — covers INFRA-03 (SQLAlchemy inspect to verify tables)
- [ ] `backend/tests/test_seed.py` — covers INFRA-04

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `docker compose ps` shows db container healthy | INFRA-01 | Requires running Docker daemon | Run `docker compose up -d --wait && docker compose ps` — look for `healthy` in status column |
| `.env.example` has no real API keys | INFRA-05 | Content review for secrets | Open `.env.example`, verify all values are placeholders (`sk-...`, `postgresql://...`) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
