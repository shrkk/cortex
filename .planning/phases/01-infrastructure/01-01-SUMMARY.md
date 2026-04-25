---
phase: 01-infrastructure
plan: 01
subsystem: testing
tags: [pytest, pytest-asyncio, httpx, fastapi, asyncio, sqlalchemy]

# Dependency graph
requires: []
provides:
  - pytest configuration with asyncio_mode = auto
  - test package scaffold (backend/tests/)
  - async httpx client fixture via ASGITransport (conftest.py)
  - INFRA-02 coverage stub: test_health_returns_ok
  - INFRA-03 coverage stubs: test_all_tables_exist, test_vector_extension_installed, test_hnsw_index_exists
  - INFRA-04 coverage stub: test_seed_creates_user_and_courses
affects: [01-02, 01-03, 01-04, 01-05, all implementation waves]

# Tech tracking
tech-stack:
  added: [pytest 9.0.3, pytest-asyncio 1.3.0, httpx 0.28.1]
  patterns:
    - asyncio_mode = auto eliminates per-test @pytest.mark.asyncio decorators
    - httpx AsyncClient + ASGITransport for in-process FastAPI testing (no live server)
    - SQLAlchemy create_async_engine + run_sync(inspect) for schema validation tests
    - Parameterized text() queries in all DB-touching tests (no string concatenation)

key-files:
  created:
    - backend/pytest.ini
    - backend/tests/__init__.py
    - backend/tests/conftest.py
    - backend/tests/test_health.py
    - backend/tests/test_migration.py
    - backend/tests/test_seed.py
  modified: []

key-decisions:
  - "Tests created in RED state — imports from app.* modules that don't exist yet; intentional per Wave 0 plan"
  - "asyncio_mode = auto in pytest.ini — required by pytest-asyncio 1.3.0 to run async tests without per-test decorator"
  - "ASGITransport pattern for health test — avoids needing live DB for unit-level health check test"
  - "Parameterized text() for all DB queries in migration/seed tests — mitigates T-1-02 tampering threat"

patterns-established:
  - "Test structure: conftest.py holds shared fixtures; each requirements area gets its own test_*.py file"
  - "DB integration tests create their own engine directly from settings.database_url; dispose after use"
  - "Health/unit tests use ASGITransport in-process; DB tests use live asyncpg connection"

requirements-completed:
  - INFRA-02
  - INFRA-03
  - INFRA-04

# Metrics
duration: 2min
completed: 2026-04-25
---

# Phase 1 Plan 01: Test Stub Scaffold Summary

**pytest 9.0.3 + pytest-asyncio test scaffold with 5 RED-state stubs covering health check, schema validation, and seed verification, establishing the Nyquist verification contract for all Wave 1+ implementation plans**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-25T21:42:17Z
- **Completed:** 2026-04-25T21:43:45Z
- **Tasks:** 2 completed
- **Files modified:** 6 created

## Accomplishments
- Created pytest.ini with asyncio_mode = auto and testpaths = tests — full async test support with no per-test decorator required
- Created async httpx client fixture (conftest.py) using ASGITransport — in-process FastAPI testing without live server
- Created 5 RED-state test stubs covering INFRA-02 (health), INFRA-03 (schema + pgvector + hnsw), INFRA-04 (seed user+courses)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create pytest config and test package scaffold** - `7f6fc7a` (chore)
2. **Task 2: Create conftest.py and three test files (RED state)** - `234746b` (test)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `backend/pytest.ini` - pytest config: asyncio_mode = auto, testpaths = tests
- `backend/tests/__init__.py` - empty Python package marker
- `backend/tests/conftest.py` - async httpx client fixture via ASGITransport
- `backend/tests/test_health.py` - INFRA-02: test_health_returns_ok (GET /health → 200 + {"status":"ok"})
- `backend/tests/test_migration.py` - INFRA-03: test_all_tables_exist (10 tables), test_vector_extension_installed, test_hnsw_index_exists
- `backend/tests/test_seed.py` - INFRA-04: test_seed_creates_user_and_courses (user_id=1 + course_count >= 1)

## Decisions Made
- Tests intentionally import from `app.*` modules that do not exist yet (RED state by design — Wave 1+ makes them GREEN)
- Used `@pytest_asyncio.fixture` (not `@pytest.fixture`) for the async client — required by pytest-asyncio 1.3.0
- All DB queries in migration/seed tests use parameterized `text()` — mitigates T-1-02 tampering threat
- DB integration tests each create and dispose their own engine — avoids fixture complexity at this stage

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## Known Stubs
Tests in this plan are intentionally RED-state stubs by design (Wave 0). They will be made GREEN by plans 01-02 through 01-05. These are not stubs in the UI/data sense — they are working test functions whose imports fail until implementation exists.

## Threat Surface Scan
No new network endpoints, auth paths, file access patterns, or schema changes introduced. All DB access in tests uses parameterized `text()` calls (T-1-02 mitigated). No real secrets in any committed file.

## Next Phase Readiness
- Test scaffold is complete and ready to receive GREEN implementations from plans 01-02 through 01-05
- Wave 1 (plan 01-02): Docker + env scaffold will provide the DB infrastructure these tests require
- Wave 2 (plan 01-03): FastAPI app wiring will satisfy `from app.main import app` import in conftest.py
- Wave 3 (plan 01-04): Alembic migration will satisfy test_migration.py assertions
- Wave 4 (plan 01-05): Seed script will satisfy test_seed.py assertions
- Full test suite expected green only after all five Wave 0–4 plans complete

## Self-Check: PASSED

Files verified present:
- backend/pytest.ini: FOUND
- backend/tests/__init__.py: FOUND
- backend/tests/conftest.py: FOUND
- backend/tests/test_health.py: FOUND
- backend/tests/test_migration.py: FOUND
- backend/tests/test_seed.py: FOUND

Commits verified:
- 7f6fc7a: FOUND (chore(01-01): create pytest config and test package scaffold)
- 234746b: FOUND (test(01-01): add RED state test stubs for INFRA-02, INFRA-03, INFRA-04)

---
*Phase: 01-infrastructure*
*Completed: 2026-04-25*
