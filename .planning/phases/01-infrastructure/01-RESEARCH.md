# Phase 1: Infrastructure - Research

**Researched:** 2026-04-25
**Domain:** FastAPI + SQLAlchemy 2.0 + Alembic + pgvector + Docker Compose — Python backend foundation
**Confidence:** HIGH

---

## Summary

Phase 1 establishes the development foundation: Postgres+pgvector running in Docker, a hand-written Alembic migration that creates all 11 tables (including `vector(1536)` columns), a FastAPI app that starts clean with a health endpoint, and a seed script that loads minimal demo data so subsequent phases have real rows to work against.

The stack is fully locked — no technology decisions remain open. The primary risk in this phase is a small set of well-documented gotchas: Alembic's autogenerate silently skips `pgvector.sqlalchemy.Vector` columns (requiring hand-written migrations), the `@app.on_event("startup")` decorator is deprecated in favor of the `lifespan` context manager, and the `pgvector/pgvector:pg16` Docker image must be used (not `postgres:16`). Every one of these has a clear prevention strategy documented here.

The seed script for Phase 1 is intentionally minimal: create `user_id=1` and 2–3 named courses so that the notch's course-matching flow has data to test against. Full demo-quality seed data (20+ concept nodes, struggle signal variance) belongs to Phase 7.

**Primary recommendation:** Write the initial Alembic migration by hand from the schema specification — do not use `alembic revision --autogenerate`. Test on `docker compose down -v && docker compose up -d && alembic upgrade head`. Use the `lifespan` context manager (not deprecated `on_event`) for the startup hook that resets `status=processing` → `status=pending`.

---

## Project Constraints (from CLAUDE.md)

The following directives from `CLAUDE.md` apply to this phase and are treated as locked:

| Directive | Implication for Phase 1 |
|-----------|------------------------|
| Docker image: `pgvector/pgvector:pg16` (NOT `postgres:16`) | docker-compose.yml must use this exact image |
| Alembic migrations: hand-written only | Never run `alembic revision --autogenerate` for this migration |
| Include `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` BEFORE table creation | First line in migration upgrade() body |
| hnsw index for `concepts.embedding` (empty-table safe) | Create in initial migration |
| Defer ivfflat for `chunks.embedding` until after seed load | Do NOT create in initial migration |
| FastAPI startup hook must reset `status=processing` → `status=pending` on boot | Use lifespan context manager |
| CORS: must allow missing Origin header (Swift URLSession sends none) | `allow_origins=["*"]` for local dev |
| Session-per-stage in pipeline (fresh AsyncSession per stage) | Applies to pipeline phases; seed script may use a single session |
| OpenAI `text-embedding-3-small` 1536-dim | `Vector(1536)` in schema |
| Anthropic claude-sonnet-4-5 for LLM tasks | Not used in Phase 1 |
| SQLAlchemy 2.0 async + Alembic for ORM/migrations | Use `AsyncSession`, `async_sessionmaker`, Alembic 1.x |

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | Docker Compose runs Postgres 16 + pgvector; `docker compose up` produces a healthy DB | `pgvector/pgvector:pg16` image, healthcheck config documented in Standard Stack |
| INFRA-02 | GET /health returns 200 with `{"status": "ok"}` | FastAPI router pattern, lifespan startup hook documented |
| INFRA-03 | Alembic migration creates all tables, indexes, and extensions in one run against a fresh DB | Hand-written migration pattern documented with full schema; pitfall C-6 addresses autogenerate failure |
| INFRA-04 | Seed script (`scripts/seed_demo.py`) loads user id=1 with pre-existing courses | Minimal seed strategy documented; async SQLAlchemy session pattern provided |
| INFRA-05 | `.env.example` documents all required environment variables | Full env var inventory documented |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Database container + pgvector extension | Docker Compose | — | Postgres runs as a container service; pgvector pre-installed in official image |
| Schema definition + migrations | Alembic (backend) | SQLAlchemy models | Alembic owns schema state; SQLAlchemy models are the Python representation |
| FastAPI app startup + health | API (FastAPI) | — | Startup hook and health route are API-layer concerns |
| Seed data loading | Backend script | API DB session | `scripts/seed_demo.py` is a standalone async script, not an API endpoint |
| Environment configuration | Local filesystem | Docker Compose env | `.env` loaded by FastAPI config; Docker Compose reads same vars for DB init |

---

## Standard Stack

### Core (Phase 1 — locked)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pgvector/pgvector:pg16` | Docker image (floating tag) | Postgres 16 + pgvector pre-installed | Official image; avoids init-script approach that fails silently |
| fastapi | 0.136.1 | Web framework | Current stable; `lifespan` context manager available since 0.93 |
| uvicorn[standard] | 0.46.0 | ASGI server | `httptools` + `websockets` extras; required for FastAPI |
| sqlalchemy | 2.0.49 | ORM + async DB | 2.0 async patterns; required by project spec |
| alembic | 1.18.4 | Schema migrations | Works with SQLAlchemy 2.0 models without shims |
| asyncpg | 0.31.0 | Async Postgres driver | Required by SQLAlchemy `async+postgresql` URL |
| psycopg2-binary | 2.9.12 | Sync Postgres driver for Alembic | Alembic's migration runner is sync-only; needs psycopg2 |
| pgvector (Python) | 0.4.2 | `Vector(1536)` type adapter for SQLAlchemy | Provides `pgvector.sqlalchemy.Vector` type |
| pydantic | 2.13.3 | Request/response schemas | FastAPI uses Pydantic v2 natively in current versions |
| python-multipart | 0.0.26 | Multipart form parsing for `/ingest` | Required by FastAPI for file uploads (Phase 2 uses this) |
| pytest | 9.0.3 | Test framework | Standard Python testing |
| pytest-asyncio | 1.3.0 | Async test support | Required for testing async FastAPI + SQLAlchemy code |

[VERIFIED: pip index versions — 2026-04-25]

### Version Notes

The prior research doc recommended `fastapi>=0.111,<0.116`. The current latest is **0.136.1** — substantially newer. The `on_event` decorator (used in the prior architecture doc's code example) was deprecated in 0.95.0 and remains functional but should not be used in new code. Use the `lifespan` context manager instead.

The `openai` SDK is now at **2.32.0** (a v2 major), which has a different client API than the 1.x assumed in prior research. See Code Examples for the correct 2.x pattern. The `anthropic` SDK is at **0.97.0**. Both are not used in Phase 1 directly but their version ranges should be pinned in `requirements.txt` now.

`trafilatura` has released **2.0.0** (a new major). Prior research recommended `>=1.6.0`. Pin to `>=2.0.0` unless Phase 2 research finds breaking changes in the 2.0 API. [ASSUMED — trafilatura 2.0 API compatibility not verified in this session]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.28.1 | Async HTTP client | Phase 2 (URL fetching); declare in requirements.txt now |
| pymupdf | 1.27.2 | PDF parsing | Phase 2; declare now |
| anthropic | 0.97.0 | Claude API client | Phase 3+; declare now |
| openai | 2.32.0 (v2) | OpenAI embeddings | Phase 2+; declare now — NOTE: v2, not v1.x |
| trafilatura | 2.0.0 | URL content extraction | Phase 2; declare now |

**Installation (Phase 1 requirements.txt):**

```bash
# Core API
fastapi==0.136.1
uvicorn[standard]==0.46.0
pydantic==2.13.3
python-multipart==0.0.26

# Database
sqlalchemy==2.0.49
alembic==1.18.4
asyncpg==0.31.0
psycopg2-binary==2.9.12
pgvector==0.4.2

# Testing
pytest==9.0.3
pytest-asyncio==1.3.0
httpx==0.28.1  # also used as async test client

# Future phases (declare now for stable requirements.txt)
pymupdf==1.27.2
anthropic==0.97.0
openai==2.32.0
trafilatura==2.0.0
```

---

## Architecture Patterns

### System Architecture Diagram

```
docker-compose.yml
  └── postgres service (pgvector/pgvector:pg16)
        └── healthcheck: pg_isready -U cortex
              │
              │ (asyncpg TCP)
              ▼
backend/app/
  ├── core/
  │   ├── config.py          ← Settings (Pydantic BaseSettings, reads .env)
  │   └── database.py        ← Engine + async_sessionmaker + get_session()
  ├── models/
  │   └── models.py          ← SQLAlchemy ORM models (all 11 tables)
  ├── api/
  │   ├── health.py          ← GET /health → {"status": "ok"}
  │   └── router.py          ← APIRouter aggregator (Phase 2+ adds more)
  └── main.py                ← FastAPI(lifespan=lifespan), include_router()

alembic/
  ├── env.py                 ← async engine setup for Alembic
  └── versions/
      └── 0001_initial.py    ← hand-written migration (CREATE EXTENSION + all tables)

scripts/
  └── seed_demo.py           ← async script: user_id=1 + 2-3 courses

.env / .env.example          ← DATABASE_URL, OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
```

**Data flow for `docker compose up` → `alembic upgrade head` → seed → health check:**

```
docker compose up -d
  → postgres container starts
  → healthcheck passes (pg_isready)

alembic upgrade head
  → env.py creates sync engine (psycopg2)
  → 0001_initial.py runs:
      CREATE EXTENSION IF NOT EXISTS vector
      CREATE TABLE users ...
      CREATE TABLE courses ...
      CREATE TABLE sources ...
      CREATE TABLE chunks ...
      CREATE TABLE concepts ...
      CREATE TABLE concept_sources ...
      CREATE TABLE extraction_cache ...
      CREATE TABLE edges ...
      CREATE TABLE flashcards ...
      CREATE TABLE quizzes ...
      CREATE INDEX concepts_embedding_idx USING hnsw ...
  → done

scripts/seed_demo.py
  → async with AsyncSession as session:
      INSERT INTO users (id) VALUES (1)
      INSERT INTO courses (user_id=1, title="CS 229") ...
      INSERT INTO courses (user_id=1, title="Test Course 2") ...
  → commit

uvicorn app.main:app
  → lifespan() runs:
      → UPDATE sources SET status='pending' WHERE status='processing'
      → yield  (app starts serving)
  → GET /health → 200 {"status": "ok"}
```

### Recommended Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + lifespan
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        # Pydantic BaseSettings
│   │   └── database.py      # Engine, async_sessionmaker, get_session()
│   ├── models/
│   │   ├── __init__.py
│   │   └── models.py        # All SQLAlchemy ORM models
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── health.py        # HealthResponse Pydantic model
│   └── api/
│       ├── __init__.py
│       ├── router.py        # Main router aggregator
│       └── health.py        # GET /health endpoint
├── alembic/
│   ├── env.py
│   ├── alembic.ini
│   └── versions/
│       └── 0001_initial.py
├── scripts/
│   └── seed_demo.py
├── tests/
│   ├── conftest.py
│   └── test_health.py
├── requirements.txt
├── .env.example
└── docker-compose.yml
```

### Pattern 1: FastAPI lifespan Context Manager (startup hook)

**What:** The modern replacement for deprecated `@app.on_event("startup")`. Handles startup + shutdown in one function. Used here to reset `status=processing` → `status=pending` on every boot.

**When to use:** Any app-level initialization or cleanup. Required by CLAUDE.md.

```python
# Source: https://fastapi.tiangolo.com/advanced/events/ [VERIFIED: web search 2026-04-25]
from contextlib import asynccontextmanager
from fastapi import FastAPI
from sqlalchemy import update
from app.core.database import AsyncSessionLocal
from app.models.models import Source

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: reset any sources stuck in 'processing' from a prior crash
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Source)
            .where(Source.status == "processing")
            .values(status="pending")
        )
        await session.commit()
    yield
    # Shutdown: nothing needed for Phase 1

app = FastAPI(lifespan=lifespan)
```

### Pattern 2: Alembic env.py for Async Engine

**What:** Alembic's migration runner is synchronous, but the application uses an async engine. `env.py` must be configured to use a sync engine (psycopg2) for migrations while the app uses asyncpg.

**When to use:** Required for all Alembic + SQLAlchemy 2.0 async projects.

```python
# alembic/env.py — synchronous migration setup
# Source: SQLAlchemy 2.0 migration guide [ASSUMED — pattern is standard]
from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
```

`alembic.ini` sqlalchemy.url should use `postgresql://` (psycopg2), NOT `postgresql+asyncpg://`.

### Pattern 3: SQLAlchemy Async Session Setup

**What:** The async engine and session factory used throughout the FastAPI app.

```python
# app/core/database.py
# Source: SQLAlchemy 2.0 async docs [ASSUMED — standard pattern]
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

engine = create_async_engine(
    settings.database_url,       # postgresql+asyncpg://...
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

Note `expire_on_commit=False` — without this, accessing ORM attributes after `commit()` in background tasks raises `DetachedInstanceError` because the session has expired the objects.

### Pattern 4: Hand-Written Alembic Migration with pgvector

**What:** The initial migration must be written by hand. Do NOT use `alembic revision --autogenerate`.

```python
# alembic/versions/0001_initial.py
# Source: CLAUDE.md directives + pgvector Python README [VERIFIED: web search 2026-04-25]
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

def upgrade():
    # MUST be first — all table CREATE statements fail without this extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table("users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("courses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("course_id", sa.Integer, sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String, nullable=False),
        sa.Column("title", sa.String),
        sa.Column("source_uri", sa.Text),
        sa.Column("raw_text", sa.Text),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("status", sa.String, server_default="pending", nullable=False),
        sa.Column("error", sa.Text),
        sa.Column("metadata", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("page_num", sa.Integer),
        sa.Column("embedding", Vector(1536)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("concepts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("course_id", sa.Integer, sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("definition", sa.Text),
        sa.Column("key_points", sa.JSON),
        sa.Column("gotchas", sa.JSON),
        sa.Column("examples", sa.JSON),
        sa.Column("related_concepts", sa.JSON),
        sa.Column("embedding", Vector(1536)),
        sa.Column("depth", sa.Integer),
        sa.Column("struggle_signals", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("concept_sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("concept_id", sa.Integer, sa.ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_questions", sa.JSON),
    )

    op.create_table("extraction_cache",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("chunk_hash", sa.String(64), nullable=False),
        sa.Column("model_version", sa.String, nullable=False),
        sa.Column("extracted_concepts", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("edges",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("from_id", sa.Integer, nullable=False),
        sa.Column("to_id", sa.Integer, nullable=False),
        sa.Column("edge_type", sa.String, nullable=False),
        sa.Column("weight", sa.Float, server_default="1.0"),
        sa.Column("metadata", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("flashcards",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("concept_id", sa.Integer, sa.ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("front", sa.Text, nullable=False),
        sa.Column("back", sa.Text, nullable=False),
        sa.Column("card_type", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table("quizzes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("course_id", sa.Integer, sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("questions", sa.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # hnsw index for concepts.embedding — works on empty table (empty-table safe)
    # CLAUDE.md: use hnsw for concepts, defer ivfflat for chunks
    op.execute("""
        CREATE INDEX concepts_embedding_idx
        ON concepts USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # extraction_cache unique index for cache lookups
    op.create_index(
        "ix_extraction_cache_chunk_model",
        "extraction_cache",
        ["chunk_hash", "model_version"],
        unique=True,
    )

    # content_hash index on sources for dedup lookups
    op.create_index("ix_sources_content_hash", "sources", ["content_hash"])

    # NOTE: ivfflat index for chunks.embedding is DEFERRED per CLAUDE.md
    # Create it in a separate migration AFTER seed data is loaded


def downgrade():
    op.drop_table("quizzes")
    op.drop_table("flashcards")
    op.drop_table("edges")
    op.drop_table("extraction_cache")
    op.drop_table("concept_sources")
    op.drop_table("concepts")
    op.drop_table("chunks")
    op.drop_table("sources")
    op.drop_table("courses")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
```

### Pattern 5: Pydantic BaseSettings for Config

**What:** All environment variables read through a single `Settings` object, validated at startup.

```python
# app/core/config.py
# Source: FastAPI docs / Pydantic v2 BaseSettings [ASSUMED — standard pattern]
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str                    # postgresql+asyncpg://...
    openai_api_key: str
    anthropic_api_key: str
    environment: str = "development"

    class Config:
        env_file = ".env"

settings = Settings()
```

Note: `pydantic-settings` is a separate package from `pydantic` in Pydantic v2. Add `pydantic-settings` to requirements.txt. [ASSUMED — this split happened at Pydantic v2]

### Pattern 6: docker-compose.yml with Healthcheck

```yaml
# docker-compose.yml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: cortex
      POSTGRES_PASSWORD: cortex
      POSTGRES_DB: cortex
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cortex -d cortex"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s

volumes:
  postgres_data:
```

### Anti-Patterns to Avoid

- **`alembic revision --autogenerate` for initial migration:** Silently skips `Vector(1536)` columns. Results in a migration that runs with no error but `embedding` columns are missing. Always hand-write.
- **`@app.on_event("startup")`:** Deprecated since FastAPI 0.95. Use `lifespan` context manager instead. Still functional but generates deprecation warnings.
- **`postgres:16` Docker image:** Requires manual pgvector extension installation via an `init.sql` file. The init script approach fails silently in some Docker Compose configurations. Use `pgvector/pgvector:pg16`.
- **Using `postgresql://` (psycopg2) for the FastAPI app database URL:** The app must use `postgresql+asyncpg://` for async operation. Only the Alembic runner (in `env.py`) should use the sync `postgresql://` URL.
- **`Vector()` without dimension argument:** Postgres accepts the column but does not enforce dimension. Mixed-dimension inserts will only fail at query time (KNN queries). Always declare as `Vector(1536)`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async DB session management | Custom connection pool | `sqlalchemy.ext.asyncio.create_async_engine` + `async_sessionmaker` | Connection pooling, health checks, proper cleanup already handled |
| Environment variable parsing | `os.environ.get()` scattered throughout | `pydantic_settings.BaseSettings` | Validation, type coercion, `.env` loading in one place |
| Database migration state tracking | Custom migration table | Alembic | Tracks applied migrations, generates upgrade/downgrade paths |
| Postgres extension installation | Manual `init.sql` via Docker entrypoint | `pgvector/pgvector:pg16` image | Extension pre-installed; init scripts have silent failure modes |
| CORS middleware | Custom headers in route handlers | `fastapi.middleware.cors.CORSMiddleware` | Handles preflight correctly, origin matching, credential handling |

**Key insight:** For a Python FastAPI + Postgres backend, the combination of SQLAlchemy 2.0 async + Alembic + asyncpg is the established production pattern. Any custom alternative adds complexity with no benefit at hackathon scale.

---

## Common Pitfalls

### Pitfall 1: Alembic autogenerate silently skips Vector columns
**What goes wrong:** `alembic revision --autogenerate` generates a migration that passes without error but creates no `embedding` columns. The migration appears to succeed. The problem is discovered later when embedding insertion fails with `column "embedding" does not exist`.
**Why it happens:** Alembic's autogenerate uses SQLAlchemy's type reflection. Postgres reports `Vector` columns as `USER-DEFINED` type, which Alembic's default comparator cannot handle.
**How to avoid:** Hand-write the initial migration. Include `from pgvector.sqlalchemy import Vector` in the migration file and use `Vector(1536)` explicitly. Test on a clean DB with `docker compose down -v && docker compose up -d && alembic upgrade head`.
**Warning signs:** `alembic upgrade head` completes without error but `\d concepts` in psql shows no `embedding` column.

### Pitfall 2: Deprecated on_event startup hook
**What goes wrong:** Code written as `@app.on_event("startup")` generates `DeprecationWarning` in FastAPI 0.136.1 and will not work in a future FastAPI version. Additionally, if both `lifespan` and `on_event` are used, the `on_event` handlers are silently ignored.
**Why it happens:** FastAPI deprecated `on_event` at 0.95.0 in favor of the `lifespan` context manager from Starlette.
**How to avoid:** Use the `@asynccontextmanager` + `lifespan=` pattern exclusively. Never mix both patterns.
**Warning signs:** `DeprecationWarning: on_event is deprecated, use lifespan event handlers` in uvicorn startup output.

### Pitfall 3: Alembic URL uses asyncpg instead of psycopg2
**What goes wrong:** Setting `sqlalchemy.url = postgresql+asyncpg://...` in `alembic.ini` causes `alembic upgrade head` to fail with event loop errors because Alembic's migration runner is synchronous.
**Why it happens:** Alembic runs migrations synchronously. `asyncpg` is an async-only driver.
**How to avoid:** Use `postgresql://` (psycopg2) in `alembic.ini`. The FastAPI app uses `postgresql+asyncpg://` in its own engine. These are separate URLs for separate purposes.
**Warning signs:** `RuntimeError: asyncio.run() cannot be called from a running event loop` when running `alembic upgrade head`.

### Pitfall 4: docker compose healthcheck not awaited before running migrations
**What goes wrong:** Running `alembic upgrade head` immediately after `docker compose up -d` can fail if Postgres hasn't finished initializing. The healthcheck in docker-compose.yml is for Docker's awareness — it doesn't automatically hold back the host shell.
**Why it happens:** `docker compose up -d` returns as soon as containers start, not when they're healthy.
**How to avoid:** Use `docker compose up -d --wait` (Docker Compose 2.x feature that waits for all services to be healthy) OR add a simple retry wrapper around the `alembic upgrade head` call in the Makefile/README.
**Warning signs:** `alembic upgrade head` fails with `connection refused` on the first run after `docker compose up -d`.

### Pitfall 5: `expire_on_commit=True` in background task sessions
**What goes wrong:** The default `expire_on_commit=True` in SQLAlchemy means all ORM object attributes are expired after `session.commit()`. If a background task accesses an ORM object after commit (e.g., to log `source.id`), it gets a `DetachedInstanceError`.
**Why it happens:** SQLAlchemy expires objects to force a fresh DB read on next access. In a closed session, that re-read is impossible.
**How to avoid:** Use `async_sessionmaker(engine, expire_on_commit=False)` in background task session factories. The Phase 1 seed script and health endpoint are not affected, but this must be set correctly now to avoid debugging later.
**Warning signs:** `DetachedInstanceError: Instance <Source> is not bound to a Session` in pipeline stage functions.

---

## Code Examples

### Health endpoint

```python
# app/api/health.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "ok"}
```

### CORS middleware (allow missing Origin for Swift URLSession)

```python
# app/main.py
# Source: CLAUDE.md + PITFALLS.md pitfall m-3 [VERIFIED: project docs]
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # allows requests with no Origin header (Swift URLSession)
    allow_credentials=False,   # must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Minimal seed script

```python
# scripts/seed_demo.py
# Source: SQLAlchemy 2.0 async patterns [ASSUMED — standard pattern]
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.models.models import User, Course
from app.core.config import settings

engine = create_async_engine(settings.database_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def seed():
    async with AsyncSessionLocal() as session:
        # user_id=1 hardcoded throughout (no auth, single-user)
        user = User(id=1)
        session.add(user)
        await session.flush()

        courses = [
            Course(user_id=1, title="CS 229 Machine Learning",
                   description="Stanford ML course"),
            Course(user_id=1, title="CS 231N Computer Vision",
                   description="Stanford CV course"),
        ]
        session.add_all(courses)
        await session.commit()
        print(f"Seeded user_id=1 with {len(courses)} courses")

if __name__ == "__main__":
    asyncio.run(seed())
```

### .env.example

```bash
# .env.example — document ALL environment variables referenced in codebase

# Database
DATABASE_URL=postgresql+asyncpg://cortex:cortex@localhost:5432/cortex
DATABASE_URL_SYNC=postgresql://cortex:cortex@localhost:5432/cortex  # for alembic.ini

# External APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# App
ENVIRONMENT=development
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `lifespan` context manager | FastAPI 0.95.0 | Prior research code examples use deprecated pattern; update all startup/shutdown logic |
| `openai>=1.30.0` (v1.x SDK) | `openai>=2.0.0` (v2.x SDK) | OpenAI SDK v2 release | API surface changed; embeddings call pattern differs |
| `fastapi>=0.111,<0.116` (prior research) | `fastapi==0.136.1` (current) | Multiple minor releases | Larger gap than anticipated; lifespan is now fully stable |
| `trafilatura>=1.6.0` (prior research) | `trafilatura==2.0.0` (current) | trafilatura 2.0 release | New major version; Phase 2 research should verify API compatibility |
| `alembic>=1.13.0` (prior research) | `alembic==1.18.4` (current) | Multiple minor releases | No breaking changes for SQLAlchemy 2.0 usage |

**OpenAI SDK v2 embeddings pattern:**

```python
# openai v2.x (NOT v1.x)
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key=settings.openai_api_key)

response = await client.embeddings.create(
    model="text-embedding-3-small",
    input=["your text here"],
)
embedding = response.data[0].embedding  # list of 1536 floats
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | Backend runtime | ✓ | 3.14.3 | — |
| pip | Package installation | ✓ | 26.0 | — |
| Docker | DB container | ✗ | — | Install Docker Desktop before Phase 1 |
| Docker Compose | DB service orchestration | ✗ | — | Same — requires Docker Desktop |
| PostgreSQL (local) | Alembic test fallback | ✗ | — | Docker only; no local install needed |

**Missing dependencies with no fallback:**
- Docker and Docker Compose are not installed on this machine. Both must be installed before Phase 1 can be executed. Docker Desktop for macOS installs both.

**Missing dependencies with fallback:**
- None

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | `backend/pytest.ini` (Wave 0 gap — create) |
| Quick run command | `pytest backend/tests/test_health.py -x` |
| Full suite command | `pytest backend/tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | DB container healthy after `docker compose up` | smoke | `docker compose ps \| grep healthy` | ❌ Wave 0 |
| INFRA-02 | GET /health returns 200 `{"status": "ok"}` | integration | `pytest tests/test_health.py::test_health_returns_ok -x` | ❌ Wave 0 |
| INFRA-03 | All tables exist after `alembic upgrade head` on fresh DB | integration | `pytest tests/test_migration.py::test_all_tables_exist -x` | ❌ Wave 0 |
| INFRA-04 | Seed script creates user_id=1 and at least one course | integration | `pytest tests/test_seed.py::test_seed_creates_user_and_courses -x` | ❌ Wave 0 |
| INFRA-05 | `.env.example` contains all vars referenced in config.py | smoke | manual review (structural check) | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest backend/tests/test_health.py -x`
- **Per wave merge:** `pytest backend/tests/ -v`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/pytest.ini` — pytest config with `asyncio_mode = auto`
- [ ] `backend/tests/__init__.py`
- [ ] `backend/tests/conftest.py` — async test DB session fixtures
- [ ] `backend/tests/test_health.py` — covers INFRA-02
- [ ] `backend/tests/test_migration.py` — covers INFRA-03 (psql `\d` equivalent via SQLAlchemy inspection)
- [ ] `backend/tests/test_seed.py` — covers INFRA-04

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No auth in v1 (user_id=1 hardcoded) |
| V3 Session Management | No | No sessions in v1 |
| V4 Access Control | No | Single-user; all data accessible |
| V5 Input Validation | Minimal | Pydantic v2 for request schemas |
| V6 Cryptography | No | No secrets at rest in Phase 1 |

**Threat patterns relevant to Phase 1:**

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| DB connection string exposure | Information Disclosure | `.env` in `.gitignore`; `.env.example` contains no real values |
| SQL injection via raw queries | Tampering | SQLAlchemy ORM / parameterized queries only |
| CORS wildcard on production | Tampering | `allow_origins=["*"]` acceptable for local dev only; document in `.env.example` |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `trafilatura 2.0.0` has a backward-compatible API with 1.x for basic `extract()` usage | Standard Stack | Phase 2 may need a different pin; update to `1.12.2` if breaking |
| A2 | `pydantic-settings` is a separate package in Pydantic v2 | Architecture Patterns (config.py) | `from pydantic_settings import BaseSettings` fails; fix by adding `pydantic-settings` to requirements.txt |
| A3 | `openai` v2.x client embeddings API uses `.embeddings.create()` as shown | Code Examples | Different method signature; would cause runtime error in Phase 2 |
| A4 | `alembic.ini` with `postgresql://` (psycopg2) for sync migrations is still the correct pattern at alembic 1.18 | Architecture Patterns | Migration runner fails; verify against alembic 1.18 docs |
| A5 | `docker compose up -d --wait` is available in Docker Compose V2 | Common Pitfalls | `--wait` flag not recognized; use `depends_on: condition: service_healthy` instead |

**If this table were empty:** All claims were verified. It is not empty — the items above warrant quick verification during Wave 0.

---

## Open Questions

1. **trafilatura 2.0 API compatibility**
   - What we know: trafilatura released 2.0.0 (verified via pip index). Prior research assumed 1.6.x.
   - What's unclear: Whether the `trafilatura.extract(url)` and `trafilatura.fetch_url(url)` interface changed in 2.0.
   - Recommendation: Phase 2 researcher should check trafilatura 2.0 changelog before pinning.

2. **`claude-sonnet-4-5` model ID availability**
   - What we know: `claude-sonnet-4-5` is referenced in CLAUDE.md, PROJECT.md, and STATE.md as the locked LLM.
   - What's unclear: Whether this exact model string is currently live in the Anthropic API (noted as a TODO in STATE.md).
   - Recommendation: Verify with `anthropic models list` or API call in Phase 3. No impact on Phase 1.

3. **`pydantic-settings` package name**
   - What we know: Pydantic v2 split settings into a separate package. `pydantic-settings` is the standard package name.
   - What's unclear: Exact package name as of pydantic 2.13.
   - Recommendation: Add `pydantic-settings` to requirements.txt; if import fails, check `pip install pydantic[email,settings]` as alternative.

---

## Sources

### Primary (HIGH confidence)
- `pip index versions` on this machine (2026-04-25) — all Python package versions verified against live PyPI registry [VERIFIED: pip index versions]
- FastAPI lifespan events official docs (web search verified 2026-04-25): https://fastapi.tiangolo.com/advanced/events/ [VERIFIED: web search]
- pgvector-python SQLAlchemy integration (web search 2026-04-25): https://github.com/pgvector/pgvector-python [VERIFIED: web search]
- CLAUDE.md project directives — locked decisions for this project [VERIFIED: file read]
- `.planning/STATE.md` — locked decisions table [VERIFIED: file read]

### Secondary (MEDIUM confidence)
- `.planning/research/STACK.md`, `ARCHITECTURE.md`, `PITFALLS.md`, `SUMMARY.md` — prior project research [CITED: project research files]
- Alembic pgvector migration patterns (web search 2026-04-25): multiple community sources confirming autogenerate skips Vector columns [VERIFIED: web search]

### Tertiary (LOW confidence — verify before use)
- trafilatura 2.0.0 API compatibility with 1.x — not verified; treat as assumed
- openai v2.x embeddings API shape — based on training knowledge; verify against SDK changelog
- pydantic-settings as separate package in pydantic v2 — training knowledge, not verified this session

---

## Metadata

**Confidence breakdown:**
- Standard stack (versions): HIGH — all verified against live PyPI via `pip index versions`
- Architecture (project structure, patterns): HIGH — based on locked CLAUDE.md decisions + FastAPI official patterns
- Alembic migration hand-write requirement: HIGH — verified via web search confirming autogenerate limitation
- FastAPI lifespan pattern: HIGH — verified via web search, official FastAPI docs
- trafilatura 2.0 compatibility: LOW — not verified; flagged as assumption A1

**Research date:** 2026-04-25
**Valid until:** 2026-05-25 (stable stack; Python package versions should be re-verified if more than 30 days pass)
