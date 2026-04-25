---
phase: 01-infrastructure
plan: 02
subsystem: backend-scaffold
tags: [docker, postgres, pgvector, fastapi, sqlalchemy, pydantic-settings, alembic]

# Dependency graph
requires:
  - 01-01 (pytest scaffold)
provides:
  - docker-compose.yml with pgvector/pgvector:pg16 and healthcheck
  - .env.example documenting all required environment variables
  - requirements.txt with exact pinned versions for all layers
  - app/core/config.py: pydantic_settings BaseSettings + settings singleton
  - app/core/database.py: async engine + AsyncSessionLocal (expire_on_commit=False) + get_session
  - app/models/models.py: 10 ORM table classes with Vector(1536) on Chunk and Concept
  - Python package structure (5 __init__.py files)
affects: [01-03, 01-04, 01-05, all subsequent phases]

# Tech tracking
tech-stack:
  added:
    - pgvector/pgvector:pg16 (Docker image)
    - pydantic-settings==2.0.0 (separate from pydantic==2.13.3)
    - sqlalchemy==2.0.49 (async engine)
    - asyncpg==0.31.0 (async Postgres driver)
    - pgvector==0.4.2 (Vector column type)
    - alembic==1.18.4 (migration runner)
  patterns:
    - expire_on_commit=False on AsyncSessionLocal prevents DetachedInstanceError in background tasks
    - pool_pre_ping=True for connection health checking before reuse
    - Mapped/mapped_column SQLAlchemy 2.0 syntax for all ORM columns
    - Vector(1536) with explicit dimension — dimensionless Vector() fails silently at query time
    - pydantic_settings.BaseSettings (not pydantic.BaseSettings) — separate package in Pydantic v2

key-files:
  created:
    - backend/docker-compose.yml
    - backend/.env.example
    - backend/.gitignore
    - backend/requirements.txt
    - backend/app/__init__.py
    - backend/app/core/__init__.py
    - backend/app/core/config.py
    - backend/app/core/database.py
    - backend/app/models/__init__.py
    - backend/app/models/models.py
    - backend/app/schemas/__init__.py
    - backend/app/api/__init__.py
  modified: []

key-decisions:
  - "pgvector/pgvector:pg16 Docker image — base postgres:16 lacks vector extension pre-built"
  - "expire_on_commit=False on session factory — prevents DetachedInstanceError in background pipeline tasks"
  - "pydantic-settings==2.0.0 separate from pydantic==2.13.3 — Pydantic v2 moved settings to distinct package"
  - "Vector(1536) explicit dimension on chunks.embedding and concepts.embedding — matches OpenAI text-embedding-3-small output"

# Metrics
duration: 2min
completed: 2026-04-25
---

# Phase 1 Plan 02: Docker Compose, Env Files, and Core Backend Modules Summary

**pgvector/pgvector:pg16 Docker Compose with healthcheck, pinned requirements.txt, pydantic_settings config, async SQLAlchemy engine with expire_on_commit=False, and 10-table ORM models with Vector(1536) on Chunk and Concept**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-25T21:47:01Z
- **Completed:** 2026-04-25T21:49:17Z
- **Tasks:** 2 completed
- **Files modified:** 12 created

## Accomplishments

- Created docker-compose.yml using `pgvector/pgvector:pg16` with pg_isready healthcheck (5s interval, 5s timeout, 5 retries, 10s start_period)
- Created .env.example documenting DATABASE_URL (asyncpg), DATABASE_URL_SYNC (psycopg2 for Alembic), OPENAI_API_KEY, ANTHROPIC_API_KEY, ENVIRONMENT
- Created requirements.txt with all packages at exact pinned versions including pydantic-settings as a separate entry from pydantic
- Created Python package scaffold: 5 __init__.py files across app/, app/core/, app/models/, app/schemas/, app/api/
- Created config.py using pydantic_settings.BaseSettings with env_file=".env" and module-level settings singleton
- Created database.py with async engine (pool_size=10, max_overflow=5, pool_pre_ping=True), AsyncSessionLocal (expire_on_commit=False), and get_session FastAPI dependency
- Created models.py defining all 10 ORM table classes with SQLAlchemy 2.0 Mapped/mapped_column syntax; Vector(1536) on chunks.embedding and concepts.embedding

## Task Commits

Each task was committed atomically:

1. **Task 1: Docker Compose, env files, requirements.txt, and directory scaffold** - `01bc557` (chore)
2. **Task 2: config.py, database.py, and models.py** - `c158722` (feat)

## Files Created/Modified

- `backend/docker-compose.yml` - pgvector/pgvector:pg16 service with healthcheck and postgres_data volume
- `backend/.env.example` - environment variable documentation with placeholder values only
- `backend/.gitignore` - excludes .env, __pycache__, .venv, .pytest_cache, .mypy_cache
- `backend/requirements.txt` - 22 pinned dependencies across API, DB, testing, and future-phase layers
- `backend/app/__init__.py` - empty package marker
- `backend/app/core/__init__.py` - empty package marker
- `backend/app/core/config.py` - pydantic_settings BaseSettings; exposes `settings` singleton
- `backend/app/core/database.py` - async engine + AsyncSessionLocal (expire_on_commit=False) + get_session
- `backend/app/models/__init__.py` - empty package marker
- `backend/app/models/models.py` - 10 ORM classes: User, Course, Source, Chunk, Concept, ConceptSource, ExtractionCache, Edge, Flashcard, Quiz
- `backend/app/schemas/__init__.py` - empty package marker
- `backend/app/api/__init__.py` - empty package marker

## Decisions Made

- Docker image is `pgvector/pgvector:pg16` — NOT `postgres:16`; base image lacks pre-built vector extension
- `expire_on_commit=False` on AsyncSessionLocal is mandatory — without it, background pipeline tasks raise DetachedInstanceError when accessing ORM attributes after commit
- `pydantic-settings==2.0.0` declared as a separate line from `pydantic==2.13.3` — Pydantic v2 extracted settings into its own package
- `Vector(1536)` with explicit dimension on both Chunk.embedding and Concept.embedding — matches OpenAI text-embedding-3-small 1536-dim output; dimensionless Vector() silently fails at query time

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## Known Stubs

None. All modules are structurally complete for their stated purpose. config.py and database.py will fail to instantiate at import time without a `.env` file present — this is expected and will be addressed when the Docker container and .env are set up (plan 01-03 wires FastAPI startup).

## Threat Surface Scan

- **T-1-01 mitigated**: `.env` is excluded by `.gitignore`; `.env.example` uses placeholder values only (`sk-...`, `sk-ant-...`) — no real credentials committed
- **T-1-02 mitigated**: All DB access in models.py uses SQLAlchemy ORM mapped_column types — no raw string concatenation in models or database.py
- No new network endpoints, auth paths, or file access patterns introduced in this plan

## Self-Check: PASSED

Files verified present:
- backend/docker-compose.yml: FOUND
- backend/.env.example: FOUND
- backend/.gitignore: FOUND
- backend/requirements.txt: FOUND
- backend/app/__init__.py: FOUND
- backend/app/core/__init__.py: FOUND
- backend/app/core/config.py: FOUND
- backend/app/core/database.py: FOUND
- backend/app/models/__init__.py: FOUND
- backend/app/models/models.py: FOUND
- backend/app/schemas/__init__.py: FOUND
- backend/app/api/__init__.py: FOUND

Commits verified:
- 01bc557: FOUND (chore(01-02): create Docker Compose, env files, requirements.txt, and app scaffold)
- c158722: FOUND (feat(01-02): add config.py, database.py, and models.py)

---
*Phase: 01-infrastructure*
*Completed: 2026-04-25*
