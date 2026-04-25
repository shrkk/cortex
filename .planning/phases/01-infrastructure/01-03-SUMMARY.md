---
phase: 01-infrastructure
plan: 03
subsystem: alembic-migrations
tags: [alembic, postgres, pgvector, hnsw, migrations, sqlalchemy]

# Dependency graph
requires:
  - 01-02 (models.py with Base.metadata, docker-compose.yml with pgvector/pgvector:pg16)
provides:
  - backend/alembic/alembic.ini: sync postgresql:// URL for Alembic migration runner
  - backend/alembic/env.py: sync migration runner importing Base.metadata with NullPool
  - backend/alembic/versions/0001_initial.py: 10-table schema + vector extension + hnsw index
  - Live database: alembic upgrade head applied, all 10 tables + hnsw index present
affects: [01-04, 01-05, all subsequent phases]

# Tech tracking
tech-stack:
  added:
    - alembic==1.18.4 (migration CLI runner)
    - psycopg2-binary==2.9.x (sync Postgres driver for Alembic; distinct from asyncpg used by FastAPI)
  patterns:
    - alembic.ini lives inside backend/alembic/ subdirectory; run with -c alembic/alembic.ini from backend/
    - CREATE EXTENSION IF NOT EXISTS vector MUST precede all Vector column CREATE TABLE statements
    - hnsw index (m=16, ef_construction=64) created on empty table — safe unlike ivfflat
    - ivfflat on chunks.embedding deferred until after seed data loads
    - SQLAlchemy Declarative API reserves 'metadata' attribute — use explicit column name mapping

key-files:
  created:
    - backend/alembic/alembic.ini
    - backend/alembic/env.py
    - backend/alembic/versions/0001_initial.py
  modified:
    - backend/app/models/models.py (Source.metadata → source_metadata, Edge.metadata → edge_metadata)
    - backend/tests/conftest.py (guard app.main import with try/except)

key-decisions:
  - "psycopg2 sync URL in alembic.ini — asyncpg is async-only; using it causes RuntimeError in synchronous migration runner"
  - "CREATE EXTENSION IF NOT EXISTS vector as first upgrade() statement — Vector column DDL fails without extension"
  - "hnsw index created in initial migration (safe on empty table); ivfflat deferred until post-seed"
  - "source_metadata / edge_metadata Python attribute names mapping to 'metadata' DB column — SQLAlchemy reserves 'metadata'"

# Metrics
duration: 6min
completed: 2026-04-25
---

# Phase 1 Plan 03: Alembic Migration Summary

**Hand-written 0001_initial.py creating 10 tables with vector extension + hnsw index on concepts.embedding; alembic upgrade head runs clean; all 3 migration tests pass**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-25T21:49:17Z
- **Completed:** 2026-04-25T21:55:24Z
- **Tasks:** 2 completed
- **Files modified:** 5 (3 created, 2 modified)

## Accomplishments

- Created alembic.ini with `script_location = alembic` and `sqlalchemy.url = postgresql://` (psycopg2 sync, not asyncpg)
- Created env.py importing `Base.metadata` as `target_metadata`, using NullPool, implementing both `run_migrations_online()` and `run_migrations_offline()`
- Hand-wrote 0001_initial.py with `CREATE EXTENSION IF NOT EXISTS vector` as the first statement, all 10 tables in FK-dependency order, hnsw index on `concepts.embedding` with m=16 ef_construction=64, UNIQUE ix_extraction_cache_chunk_model, ix_sources_content_hash; no ivfflat
- Ran `alembic upgrade head` against live Docker Compose database — exits 0
- pytest tests/test_migration.py -v: **3 passed** (tables_exist, vector_extension, hnsw_index)

## Task Commits

1. **Task 1: alembic.ini and env.py** - `bab22e6` (chore)
2. **Task 2: Hand-write 0001_initial.py migration and run it** - `d3a3fe1` (feat)

## Files Created/Modified

- `backend/alembic/alembic.ini` - Alembic configuration with sync postgresql:// URL
- `backend/alembic/env.py` - Sync migration runner with Base.metadata and NullPool
- `backend/alembic/versions/0001_initial.py` - Initial schema migration: 10 tables + vector extension + hnsw index
- `backend/app/models/models.py` - Fixed reserved 'metadata' attribute name on Source and Edge models
- `backend/tests/conftest.py` - Guarded app.main import to unblock migration tests

## Decisions Made

- `sqlalchemy.url` must use `postgresql://` (psycopg2), not `postgresql+asyncpg://` — Alembic's migration runner is synchronous; asyncpg raises RuntimeError in sync context
- `CREATE EXTENSION IF NOT EXISTS vector` must be the FIRST statement in upgrade() — Vector column DDL silently fails if the extension is not loaded first
- hnsw index (`m=16, ef_construction=64`) is safe on an empty table; ivfflat is intentionally deferred until after seed data loads (ivfflat has near-zero recall on empty table)
- SQLAlchemy's Declarative API reserves the `metadata` attribute on all mapped classes; renaming to `source_metadata` / `edge_metadata` with explicit `mapped_column("metadata", JSON)` preserves the DB column name

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reserved 'metadata' attribute name on SQLAlchemy ORM models**
- **Found during:** Task 2 (when running alembic upgrade head)
- **Issue:** `sqlalchemy.exc.InvalidRequestError: Attribute name 'metadata' is reserved when using the Declarative API` — Source and Edge models both had a column named `metadata`
- **Fix:** Renamed Python attributes to `source_metadata` and `edge_metadata` with explicit column name `"metadata"` in `mapped_column("metadata", JSON)` — DB column name unchanged
- **Files modified:** `backend/app/models/models.py`
- **Commit:** `d3a3fe1`

**2. [Rule 3 - Blocker] conftest.py imports app.main which doesn't exist until plan 01-04**
- **Found during:** Task 2 (when running pytest tests/test_migration.py)
- **Issue:** `ModuleNotFoundError: No module named 'app.main'` — conftest.py top-level import failed, blocking all tests in the suite
- **Fix:** Wrapped the httpx + app.main import in `try/except ImportError` — migration tests run without the fixture; health tests will use it once app.main is created in plan 01-04
- **Files modified:** `backend/tests/conftest.py`
- **Commit:** `d3a3fe1`

## Known Stubs

None. All migration files and DB schema are structurally complete.

## Threat Surface Scan

- **T-1-01 reviewed**: `alembic.ini` hardcodes `cortex:cortex@localhost` (local dev credentials only); file is not in .gitignore because it contains no production secrets — consistent with the plan's accepted disposition
- No new network endpoints or auth paths introduced in this plan

## Self-Check: PASSED

Files verified present:
- backend/alembic/alembic.ini: FOUND
- backend/alembic/env.py: FOUND
- backend/alembic/versions/0001_initial.py: FOUND

Commits verified:
- bab22e6: FOUND (chore(01-03): add alembic.ini and env.py)
- d3a3fe1: FOUND (feat(01-03): hand-write 0001_initial.py migration and run upgrade head)

Migration verified:
- alembic upgrade head: exits 0 — "Running upgrade  -> 0001, initial schema"
- pytest tests/test_migration.py -v: 3 passed

---
*Phase: 01-infrastructure*
*Completed: 2026-04-25*
