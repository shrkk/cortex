---
phase: 01-infrastructure
plan: 05
subsystem: database
tags: [sqlalchemy, asyncpg, postgresql, seed, pgvector, pytest]

# Dependency graph
requires:
  - 01-02 (User and Course ORM models, settings.database_url)
  - 01-03 (migrated DB with all 10 tables + vector extension + hnsw index)
  - 01-04 (FastAPI app running for test_health_returns_ok)
provides:
  - backend/scripts/seed_demo.py: async idempotent seed script — user_id=1 + 2 named courses
  - Phase gate: all 5 INFRA pytest tests passing (health + 3 migration + seed)
affects: [phase-2, phase-3, phase-4, phase-5, phase-6, phase-7]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - pg_insert ON CONFLICT DO NOTHING for idempotent upsert of integer PK rows
    - sys.path.insert(0, parent) pattern for standalone scripts that import app modules
    - async_sessionmaker(engine, expire_on_commit=False) consistent with database.py

key-files:
  created:
    - backend/scripts/seed_demo.py
  modified: []

key-decisions:
  - "ON CONFLICT DO NOTHING on users.id — idempotent user insert safe to re-run"
  - "Course insert guarded by count check — avoids duplicate courses on re-runs"
  - "sys.path.insert for standalone script — no editable install needed in dev"

patterns-established:
  - "Seed scripts use pg_insert (dialect-specific) for ON CONFLICT DO NOTHING semantics"
  - "Standalone scripts prepend parent dir to sys.path for app module resolution"

requirements-completed: [INFRA-04]

# Metrics
duration: 2min
completed: 2026-04-25
---

# Phase 1 Plan 05: Seed Script + Full Phase Gate Summary

**Async idempotent seed script inserts user_id=1 and 2 named courses (CS 229 ML, CS 231N CV); all 5 INFRA phase-gate tests pass (health + 3 migration + seed)**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-25T22:02:04Z
- **Completed:** 2026-04-25T22:04:00Z
- **Tasks:** 1 completed
- **Files modified:** 1 (created)

## Accomplishments

- Created `backend/scripts/seed_demo.py` with async SQLAlchemy insert using `pg_insert(...).on_conflict_do_nothing(index_elements=["id"])` for user_id=1
- Course insert guarded by count check — idempotent, safe to re-run multiple times
- `python scripts/seed_demo.py` exits 0, prints "Seeded user_id=1 with 2 courses."
- Full phase gate: 5/5 pytest tests green (test_health_returns_ok, test_all_tables_exist, test_vector_extension_installed, test_hnsw_index_exists, test_seed_creates_user_and_courses)

## Task Commits

1. **Task 1: Create seed_demo.py and run full phase verification** - `a1151b2` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `backend/scripts/seed_demo.py` - Async seed script: user_id=1 + CS 229 ML + CS 231N CV courses

## Decisions Made

- `pg_insert(User).values(id=1).on_conflict_do_nothing(index_elements=["id"])` chosen over ORM `merge()` — explicit dialect-specific upsert is clearer and avoids ORM state complexity on PK conflict
- Course idempotency via count check (`SELECT COUNT(*) WHERE user_id = 1`) rather than per-title conflict — simpler and sufficient for Phase 1 minimal seed
- `expire_on_commit=False` on `async_sessionmaker` — consistent with the `database.py` pattern established in Plan 02, prevents DetachedInstanceError if ORM attributes accessed post-commit

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. Seed data is real rows committed to the live DB.

## Threat Surface Scan

- T-1-01 (credentials): seed script reads DB credentials only via `settings.database_url` from pydantic-settings — no hardcoded credentials
- T-1-02 (DB writes): `ON CONFLICT DO NOTHING` on users.id; course insert is additive only — no destructive writes
- No new network endpoints or trust boundaries introduced

## Phase Gate Results

All 5 INFRA requirements satisfied:

| Requirement | Test | Result |
|-------------|------|--------|
| INFRA-01: Docker DB healthy | `docker compose ps` shows `healthy` | PASS |
| INFRA-02: GET /health returns 200 | `test_health_returns_ok` | PASS |
| INFRA-03: All tables + vector + hnsw | `test_all_tables_exist`, `test_vector_extension_installed`, `test_hnsw_index_exists` | PASS (3/3) |
| INFRA-04: Seed data loaded | `test_seed_creates_user_and_courses` | PASS |
| INFRA-05: .env.example complete | DATABASE_URL, DATABASE_URL_SYNC, OPENAI_API_KEY, ANTHROPIC_API_KEY, ENVIRONMENT present | PASS |

## Self-Check: PASSED

Files verified present:
- backend/scripts/seed_demo.py: FOUND

Commits verified:
- a1151b2: FOUND (feat(01-05): add async seed script for user_id=1 and 2 named courses)

Tests verified:
- pytest tests/ -v: 5 passed

## Next Phase Readiness

Phase 1 — Infrastructure is complete. All 5 plans executed, all 5 INFRA requirements satisfied.

Phase 2 (Ingest + Parsing + Notch) can begin:
- DB is live with pgvector extension and hnsw index
- All 10 tables migrated and accessible
- user_id=1 exists with 2 named courses for course-matching pre-flight
- FastAPI app boots clean with startup reconciliation hook
- Full test suite green as baseline

---
*Phase: 01-infrastructure*
*Completed: 2026-04-25*
