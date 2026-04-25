---
phase: 01-infrastructure
verified: 2026-04-25T22:10:49Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification: false
human_verification:
  - test: "Run `docker compose down -v && docker compose up -d --wait` then `alembic upgrade head` against the fresh empty DB and confirm exit 0 and `docker compose ps` shows healthy"
    expected: "All 10 tables created, vector extension installed, hnsw index on concepts.embedding present; db container shows (healthy)"
    why_human: "Verifier cannot destroy and recreate the live Docker volume to test a truly fresh-DB upgrade path. The current DB is already migrated; we can only confirm the migration file content and that tests pass against the live DB, not that the DDL runs cleanly from scratch."
  - test: "Start the API server with `uvicorn app.main:app` (from backend/) and issue `curl http://localhost:8000/health`"
    expected: "HTTP 200 with body `{\"status\": \"ok\"}`; no DeprecationWarning lines in server startup output (only the Pydantic class-Config warning is acceptable)"
    why_human: "The test_health_returns_ok test uses ASGITransport (in-process); the verifier cannot start a real uvicorn process to confirm real-server behavior and clean startup output."
---

# Phase 1: Infrastructure Verification Report

**Phase Goal:** The development foundation is solid — a fresh `docker compose up` produces a healthy Postgres+pgvector database with all tables, indexes, and extensions in place, and the API server starts clean with a passing health check.
**Verified:** 2026-04-25T22:10:49Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `docker compose up -d` completes without error and DB container shows healthy | VERIFIED | `docker compose ps` shows `backend-db-1 pgvector/pgvector:pg16 Up 16 minutes (healthy)`; healthcheck configured with `pg_isready -U cortex -d cortex` |
| 2 | `alembic upgrade head` on a fresh DB creates all tables, vector extension, hnsw index, and all FKs | VERIFIED | `0001_initial.py` hand-written with `CREATE EXTENSION IF NOT EXISTS vector` as first statement; 10 tables in FK-dependency order; hnsw index `concepts_embedding_idx` with `m=16, ef_construction=64`; `test_all_tables_exist`, `test_vector_extension_installed`, `test_hnsw_index_exists` all PASS against live DB |
| 3 | `GET /health` returns HTTP 200 `{"status": "ok"}` | VERIFIED | `test_health_returns_ok` PASSES via ASGITransport in-process test; `health.py` returns `HealthResponse(status="ok")`; route wired through `router.py` → `main.py` |
| 4 | `scripts/seed_demo.py` runs against the migrated DB and produces at least one course row and user_id=1 | VERIFIED | `test_seed_creates_user_and_courses` PASSES; seed script inserts `User(id=1)` with `ON CONFLICT DO NOTHING`; inserts CS 229 ML and CS 231N CV courses; idempotent |
| 5 | `.env.example` is present and documents every environment variable referenced in the codebase | VERIFIED | `.env.example` documents `DATABASE_URL`, `DATABASE_URL_SYNC`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `ENVIRONMENT` — all 5 variables referenced in `config.py` Settings class |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/docker-compose.yml` | pgvector/pgvector:pg16 container with healthcheck | VERIFIED | Uses `pgvector/pgvector:pg16`; healthcheck `pg_isready -U cortex -d cortex`; `start_period: 10s` |
| `backend/.env.example` | Environment variable documentation | VERIFIED | All 5 required vars present with placeholder values; no real secrets |
| `backend/requirements.txt` | Pinned dependency list | VERIFIED | `fastapi==0.136.1`, `pydantic==2.13.3`, `pydantic-settings==2.0.0`, `pgvector==0.4.2`, `pytest-asyncio==1.3.0` all present at exact versions |
| `backend/app/core/config.py` | Pydantic BaseSettings config | VERIFIED | `from pydantic_settings import BaseSettings`; `env_file = ".env"`; `settings = Settings()` singleton |
| `backend/app/core/database.py` | Async engine + session factory + get_session | VERIFIED | `pool_pre_ping=True`; `expire_on_commit=False`; `async def get_session()` |
| `backend/app/models/models.py` | All 10 SQLAlchemy ORM models | VERIFIED | All 10 classes defined: User, Course, Source, Chunk, Concept, ConceptSource, ExtractionCache, Edge, Flashcard, Quiz; `Vector(1536)` on Chunk.embedding and Concept.embedding |
| `backend/alembic/alembic.ini` | Alembic config with sync postgresql:// URL | VERIFIED | `sqlalchemy.url = postgresql://cortex:cortex@localhost:5432/cortex` (psycopg2, no asyncpg) |
| `backend/alembic/env.py` | Sync migration runner with Base.metadata | VERIFIED | `from app.models.models import Base`; `target_metadata = Base.metadata`; `poolclass=pool.NullPool` |
| `backend/alembic/versions/0001_initial.py` | Hand-written initial migration | VERIFIED | `CREATE EXTENSION IF NOT EXISTS vector` is first statement; `concepts_embedding_idx` hnsw index; `ix_extraction_cache_chunk_model` unique; `ix_sources_content_hash`; no ivfflat |
| `backend/app/main.py` | FastAPI app with lifespan, CORS, router | VERIFIED | `@asynccontextmanager` lifespan; no `@app.on_event`; `allow_origins=["*"]` with `allow_credentials=False`; startup hook resets processing→pending |
| `backend/app/api/health.py` | GET /health endpoint | VERIFIED | Returns `HealthResponse(status="ok")`; wired via router |
| `backend/app/api/router.py` | Aggregator router | VERIFIED | `router.include_router(health.router, tags=["health"])` |
| `backend/app/schemas/health.py` | HealthResponse model | VERIFIED | `class HealthResponse(BaseModel): status: str` |
| `backend/scripts/seed_demo.py` | Async seed script | VERIFIED | Idempotent; `User(id=1)` with `on_conflict_do_nothing`; 2 named courses; `expire_on_commit=False` |
| `backend/pytest.ini` | pytest config with asyncio_mode=auto | VERIFIED | `asyncio_mode = auto`; `testpaths = tests` |
| `backend/tests/conftest.py` | AsyncClient fixture | VERIFIED | `ASGITransport(app=app)` with try/except guard for migration test isolation |
| `backend/tests/test_health.py` | INFRA-02 coverage | VERIFIED | `test_health_returns_ok` asserts 200 + `{"status": "ok"}` |
| `backend/tests/test_migration.py` | INFRA-03 coverage | VERIFIED | `test_all_tables_exist`, `test_vector_extension_installed`, `test_hnsw_index_exists` |
| `backend/tests/test_seed.py` | INFRA-04 coverage | VERIFIED | `test_seed_creates_user_and_courses` asserts user_id=1 and course_count >= 1 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `app/core/config.py` | `.env` | `env_file = ".env"` in class Config | WIRED | Pattern confirmed in config.py line 12 |
| `app/core/database.py` | `app/core/config.py` | `from app.core.config import settings` | WIRED | Line 3 of database.py |
| `app/models/models.py` | pgvector | `from pgvector.sqlalchemy import Vector` | WIRED | Line 3 of models.py; `Vector(1536)` used on Chunk and Concept |
| `alembic/alembic.ini` | Postgres via psycopg2 | `sqlalchemy.url = postgresql://` | WIRED | Non-comment lines only use psycopg2 URL |
| `alembic/env.py` | `app/models/models.py` | `from app.models.models import Base; target_metadata = Base.metadata` | WIRED | Lines 7 and 16 of env.py |
| `alembic/versions/0001_initial.py` | pgvector | `from pgvector.sqlalchemy import Vector` | WIRED | Line 3 of migration |
| `app/main.py` | `app/core/database.py` | `from app.core.database import AsyncSessionLocal` | WIRED | Line 7 of main.py |
| `app/main.py` | `app/models/models.py` | `from app.models.models import Source` | WIRED | Line 8 of main.py |
| `app/main.py` | `app/api/router.py` | `from app.api.router import router; app.include_router(router)` | WIRED | Lines 9 and 48 of main.py |
| `app/api/router.py` | `app/api/health.py` | `router.include_router(health.router)` | WIRED | Line 10 of router.py |
| `scripts/seed_demo.py` | `app/models/models.py` | `from app.models.models import User, Course` | WIRED | Line 29 of seed_demo.py |
| `scripts/seed_demo.py` | `app/core/config.py` | `from app.core.config import settings` | WIRED | Line 30 of seed_demo.py |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `app/api/health.py` | `HealthResponse(status="ok")` | Hardcoded constant | N/A — intentional static response | FLOWING (health endpoint has no DB dependency by design) |
| `scripts/seed_demo.py` | `user_row`, `course_count` | `pg_insert(User)` + `session.add_all(courses)` → live DB commit | Yes — writes to live asyncpg connection | FLOWING |
| `tests/test_migration.py` | `table_names`, `row` | SQLAlchemy `inspect(sync_conn).get_table_names()` + `pg_extension` query | Yes — queries live DB | FLOWING |
| `tests/test_seed.py` | `user_row`, `course_count` | Parameterized `text()` queries against live DB | Yes — queries live users/courses tables | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 5/5 pytest tests pass (full phase gate) | `cd backend && python -m pytest tests/ -v` | `5 passed, 1 warning in 0.13s` | PASS |
| Docker DB container healthy | `docker compose ps` | `backend-db-1 Up (healthy)` | PASS |
| FastAPI app imports cleanly | `python -c "from app.main import app; print(app.title)"` | `Cortex API` | PASS |
| Settings class loads | `python -c "from app.core.config import Settings; print('OK')"` | `Settings imports OK` | PASS |
| No asyncpg in alembic.ini DDL path | grep on non-comment lines | No asyncpg in functional config | PASS |
| No ivfflat DDL in migration | grep on migration file | ivfflat only in comments, not DDL | PASS |
| No on_event in main.py | grep on main.py | No matches | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| INFRA-01 | 01-02 | Docker Compose runs Postgres 16 + pgvector; `docker compose up` produces healthy DB | SATISFIED | `docker compose ps` shows `backend-db-1` with `(healthy)` status; `pgvector/pgvector:pg16` image confirmed |
| INFRA-02 | 01-01, 01-04 | GET /health returns 200 with `{"status": "ok"}` | SATISFIED | `test_health_returns_ok` PASSES; `health.py` returns `HealthResponse(status="ok")` |
| INFRA-03 | 01-01, 01-03 | Alembic migration creates all tables, indexes, and extensions | SATISFIED | `test_all_tables_exist` (10 tables), `test_vector_extension_installed`, `test_hnsw_index_exists` all PASS |
| INFRA-04 | 01-01, 01-05 | Seed script loads user_id=1 with pre-existing courses | SATISFIED | `test_seed_creates_user_and_courses` PASSES; seed inserts User(id=1) + 2 named courses idempotently |
| INFRA-05 | 01-02 | `.env.example` documents all required environment variables | SATISFIED | `.env.example` has `DATABASE_URL`, `DATABASE_URL_SYNC`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `ENVIRONMENT` |

All 5 INFRA requirements are satisfied by evidence in the codebase and passing tests.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/core/config.py` | 11–13 | `class Config:` (Pydantic v2 deprecated style) | Info | Pydantic v2 prefers `model_config = ConfigDict(env_file=".env")` over `class Config`; emits `PydanticDeprecatedSince20` warning at import time but is **fully functional** — settings load correctly |

No blockers or critical anti-patterns found. The Pydantic `class Config` style is a cosmetic deprecation warning — the code works correctly and will not break until Pydantic v3.

---

### Human Verification Required

### 1. Fresh-DB Migration Test

**Test:** Run `docker compose down -v && docker compose up -d --wait` then `cd backend && alembic upgrade head` and verify the output ends with `Running upgrade  -> 0001, initial schema` and exits 0. Then run `pytest tests/test_migration.py -v` and confirm 3 tests pass.
**Expected:** All DDL runs cleanly from a completely empty database; `alembic_version` table shows `0001`; all 10 tables, vector extension, and hnsw index are present.
**Why human:** The verifier cannot safely destroy the existing Docker volume (`docker compose down -v` would wipe the live seeded database). The migration file content and current passing tests are strong evidence, but the "fresh DB" requirement from ROADMAP Success Criterion #2 strictly requires a clean-slate test.

### 2. Live Server Health Check

**Test:** From `backend/`, run `uvicorn app.main:app --port 8001` and issue `curl -s http://localhost:8001/health`.
**Expected:** JSON response `{"status":"ok"}` with HTTP 200; uvicorn startup logs show no ERROR lines (only the Pydantic class-Config deprecation warning is acceptable).
**Why human:** `test_health_returns_ok` uses ASGITransport (in-process, no network stack). The verifier cannot start a persistent uvicorn process to confirm end-to-end HTTP behavior through the network stack.

---

### Gaps Summary

No blocking gaps found. All 5 INFRA requirements are implemented correctly and verified by passing tests against the live database. The 2 human verification items are follow-through confirmations for requirements that are substantially proven but cannot be fully automated without destructive operations or a live server.

**Notable deviation documented:** `models.py` had SQLAlchemy reserved attribute name conflict on `Source.metadata` and `Edge.metadata` — auto-fixed during plan 01-03 by renaming Python attributes to `source_metadata`/`edge_metadata` while preserving the DB column name `"metadata"`. This is correctly reflected in the migration (column name `metadata` in DDL) and in models.py (explicit `mapped_column("metadata", JSON)`).

---

_Verified: 2026-04-25T22:10:49Z_
_Verifier: Claude (gsd-verifier)_
