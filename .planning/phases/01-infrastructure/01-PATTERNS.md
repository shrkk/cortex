# Phase 1: Infrastructure - Pattern Map

**Mapped:** 2026-04-25
**Files analyzed:** 22 (all new — brand-new project)
**Analogs found:** 0 / 22 (no existing source code; all patterns sourced from RESEARCH.md)

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `backend/docker-compose.yml` | config | — | No existing analog | none |
| `backend/.env.example` | config | — | No existing analog | none |
| `backend/requirements.txt` | config | — | No existing analog | none |
| `backend/app/__init__.py` | config | — | No existing analog | none |
| `backend/app/main.py` | config / entry-point | request-response | No existing analog | none |
| `backend/app/core/__init__.py` | config | — | No existing analog | none |
| `backend/app/core/config.py` | config | — | No existing analog | none |
| `backend/app/core/database.py` | utility | CRUD | No existing analog | none |
| `backend/app/models/__init__.py` | config | — | No existing analog | none |
| `backend/app/models/models.py` | model | CRUD | No existing analog | none |
| `backend/app/schemas/__init__.py` | config | — | No existing analog | none |
| `backend/app/schemas/health.py` | model | request-response | No existing analog | none |
| `backend/app/api/__init__.py` | config | — | No existing analog | none |
| `backend/app/api/router.py` | route | request-response | No existing analog | none |
| `backend/app/api/health.py` | controller | request-response | No existing analog | none |
| `backend/alembic/env.py` | config | batch | No existing analog | none |
| `backend/alembic/alembic.ini` | config | — | No existing analog | none |
| `backend/alembic/versions/0001_initial.py` | migration | batch | No existing analog | none |
| `backend/scripts/seed_demo.py` | utility | CRUD | No existing analog | none |
| `backend/tests/conftest.py` | test | — | No existing analog | none |
| `backend/tests/test_health.py` | test | request-response | No existing analog | none |
| `backend/pytest.ini` | config | — | No existing analog | none |

---

## Pattern Assignments

All patterns below are sourced directly from `01-RESEARCH.md` code examples and architecture patterns — there is no existing application code to copy from.

---

### `backend/docker-compose.yml` (config)

**Source:** RESEARCH.md Pattern 6

**Critical constraint:** Use `pgvector/pgvector:pg16` NOT `postgres:16`. The official pgvector image has the extension pre-installed; the vanilla Postgres image requires a fragile init-script approach.

**Full file pattern:**
```yaml
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

---

### `backend/.env.example` (config)

**Source:** RESEARCH.md Code Examples — .env.example

**Critical constraint:** Contains no real secrets. All values are placeholders. `.env` must be in `.gitignore`.

**Full file pattern:**
```bash
# Database
DATABASE_URL=postgresql+asyncpg://cortex:cortex@localhost:5432/cortex
DATABASE_URL_SYNC=postgresql://cortex:cortex@localhost:5432/cortex  # for alembic.ini

# External APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# App
ENVIRONMENT=development
```

**Note:** Two separate URLs — one for the async FastAPI app (`postgresql+asyncpg://`), one for the sync Alembic runner (`postgresql://`). These serve different purposes and must never be swapped.

---

### `backend/requirements.txt` (config)

**Source:** RESEARCH.md Standard Stack — Installation

**Full file pattern:**
```
# Core API
fastapi==0.136.1
uvicorn[standard]==0.46.0
pydantic==2.13.3
pydantic-settings==2.0.0
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

**Note:** `pydantic-settings` is a separate package from `pydantic` in Pydantic v2. Must be added explicitly. See RESEARCH.md assumption A2.

---

### `backend/app/__init__.py` (config)

Empty file. Standard Python package marker.

---

### `backend/app/main.py` (entry-point, request-response)

**Source:** RESEARCH.md Pattern 1 (lifespan) + Code Examples (CORS)

**Critical constraints:**
- Use `lifespan` context manager — NOT deprecated `@app.on_event("startup")`
- Startup hook must reset `status='processing'` → `status='pending'`
- CORS must use `allow_origins=["*"]` with `allow_credentials=False` (Swift URLSession sends no Origin header)

**Imports pattern:**
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import update
from app.core.database import AsyncSessionLocal
from app.models.models import Source
from app.api.router import router
```

**Lifespan pattern:**
```python
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

**CORS middleware pattern:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # allows requests with no Origin header (Swift URLSession)
    allow_credentials=False,   # must be False when allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
```

---

### `backend/app/core/__init__.py` (config)

Empty file. Standard Python package marker.

---

### `backend/app/core/config.py` (config)

**Source:** RESEARCH.md Pattern 5

**Critical constraint:** Import from `pydantic_settings`, not `pydantic`. The split happened at Pydantic v2.

**Full file pattern:**
```python
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

---

### `backend/app/core/database.py` (utility, CRUD)

**Source:** RESEARCH.md Pattern 3

**Critical constraints:**
- `expire_on_commit=False` — required to prevent `DetachedInstanceError` in background tasks
- `pool_pre_ping=True` — ensures stale connections are detected before use
- `get_session()` yields — used as a FastAPI dependency via `Depends(get_session)`

**Full file pattern:**
```python
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

---

### `backend/app/models/__init__.py` (config)

Empty file. Standard Python package marker.

---

### `backend/app/models/models.py` (model, CRUD)

**Source:** RESEARCH.md Pattern 4 (column definitions extracted from migration)

**Critical constraints:**
- `Vector(1536)` — always include dimension; dimensionless Vector columns fail silently at query time
- All tables inherit from `Base = DeclarativeBase()`
- Use `mapped_column` and `Mapped` from SQLAlchemy 2.0 (not legacy `Column`)

**Imports pattern:**
```python
from sqlalchemy import Integer, String, Text, DateTime, Float, JSON, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
```

**Base class pattern:**
```python
class Base(DeclarativeBase):
    pass
```

**Table definitions follow the schema from RESEARCH.md Pattern 4.** The 11 tables are:
- `users` — id, created_at
- `courses` — id, user_id (FK→users, CASCADE), title, description, created_at
- `sources` — id, course_id (FK→courses, CASCADE), source_type, title, source_uri, raw_text, content_hash(64), status(default='pending'), error, metadata(JSON), created_at
- `chunks` — id, source_id (FK→sources, CASCADE), text, page_num, embedding(Vector(1536)), created_at
- `concepts` — id, course_id (FK→courses, CASCADE), title, definition, key_points(JSON), gotchas(JSON), examples(JSON), related_concepts(JSON), embedding(Vector(1536)), depth, struggle_signals(JSON), created_at
- `concept_sources` — id, concept_id (FK→concepts, CASCADE), source_id (FK→sources, CASCADE), student_questions(JSON)
- `extraction_cache` — id, chunk_hash(64), model_version, extracted_concepts(JSON), created_at
- `edges` — id, from_id, to_id, edge_type, weight(default=1.0), metadata(JSON), created_at
- `flashcards` — id, concept_id (FK→concepts, CASCADE), front, back, card_type, created_at
- `quizzes` — id, course_id (FK→courses, CASCADE), questions(JSON), created_at

**Note:** `chunks` and `concepts` are the only tables with `Vector(1536)` embedding columns.

---

### `backend/app/schemas/__init__.py` (config)

Empty file. Standard Python package marker.

---

### `backend/app/schemas/health.py` (model, request-response)

**Source:** RESEARCH.md Code Examples — health endpoint

**Full file pattern:**
```python
from pydantic import BaseModel

class HealthResponse(BaseModel):
    status: str
```

---

### `backend/app/api/__init__.py` (config)

Empty file. Standard Python package marker.

---

### `backend/app/api/router.py` (route, request-response)

**Source:** RESEARCH.md Architecture Patterns (router aggregator role)

**Pattern — aggregator router that grows with each phase:**
```python
from fastapi import APIRouter
from app.api import health

router = APIRouter()
router.include_router(health.router, tags=["health"])
```

**Note:** Phase 2+ will add `courses`, `ingest`, `graph` routers here by appending `router.include_router(...)` lines.

---

### `backend/app/api/health.py` (controller, request-response)

**Source:** RESEARCH.md Code Examples — health endpoint

**Full file pattern:**
```python
from fastapi import APIRouter
from app.schemas.health import HealthResponse

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health():
    return {"status": "ok"}
```

---

### `backend/alembic/env.py` (config, batch)

**Source:** RESEARCH.md Pattern 2

**Critical constraints:**
- Must use sync psycopg2 engine — NOT asyncpg. Alembic's runner is synchronous.
- `target_metadata` must point to the ORM `Base.metadata` for future autogenerate (even though Phase 1 migration is hand-written)
- `sqlalchemy.url` in `alembic.ini` must use `postgresql://` scheme

**Full file pattern:**
```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from app.models.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

---

### `backend/alembic/alembic.ini` (config)

**Source:** RESEARCH.md Pattern 2 + Pitfall 3

**Critical constraint:** `sqlalchemy.url` must use `postgresql://` (psycopg2 sync URL), NOT `postgresql+asyncpg://`. Using asyncpg here causes `RuntimeError: asyncio.run() cannot be called from a running event loop`.

**Key lines pattern:**
```ini
[alembic]
script_location = alembic
prepend_sys_path = .

[alembic:exclude]
# Do not autogenerate — hand-write only (Vector columns are skipped by autogenerate)

[logger_root]
level = WARN
handlers = console

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

**Note:** `sqlalchemy.url` should be set to `%(DATABASE_URL_SYNC)s` (read from env) OR hardcoded as `postgresql://cortex:cortex@localhost:5432/cortex` for local dev. The env-var approach is preferred to avoid committing credentials.

---

### `backend/alembic/versions/0001_initial.py` (migration, batch)

**Source:** RESEARCH.md Pattern 4 (complete migration)

**Critical constraints:**
- `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` MUST be the first statement in `upgrade()` — all Vector column creates fail without the extension
- `Vector(1536)` — always with dimension
- hnsw index for `concepts.embedding` — safe on empty table; create in this migration
- ivfflat index for `chunks.embedding` — DEFERRED; do NOT create in this migration (requires data)
- Do NOT use `alembic revision --autogenerate` — hand-write only

**File header pattern:**
```python
"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-25

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None
```

**upgrade() opening — always first:**
```python
def upgrade():
    # MUST be first — all table CREATE statements fail without this extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table("users", ...)
    # ... all 10 remaining tables ...

    # hnsw index for concepts.embedding — works on empty table
    op.execute("""
        CREATE INDEX concepts_embedding_idx
        ON concepts USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # extraction_cache unique index
    op.create_index(
        "ix_extraction_cache_chunk_model",
        "extraction_cache",
        ["chunk_hash", "model_version"],
        unique=True,
    )

    # content_hash index on sources for dedup
    op.create_index("ix_sources_content_hash", "sources", ["content_hash"])

    # NOTE: ivfflat index for chunks.embedding is DEFERRED — create AFTER seed data
```

**downgrade() pattern — reverse table creation order (children before parents):**
```python
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

The full column-by-column table definitions are in RESEARCH.md Pattern 4 (lines 342–468). Copy verbatim.

---

### `backend/scripts/seed_demo.py` (utility, CRUD)

**Source:** RESEARCH.md Code Examples — Minimal seed script

**Critical constraints:**
- Standalone async script — NOT invoked via API endpoint
- `user_id=1` hardcoded (no auth in v1; single-user app)
- `expire_on_commit=False` on session factory
- Minimal seed: 1 user + 2–3 named courses (full demo data belongs to Phase 7)

**Full file pattern:**
```python
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

---

### `backend/tests/conftest.py` (test)

**Source:** RESEARCH.md Validation Architecture + standard pytest-asyncio patterns

**Pattern — async test session fixture:**
```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
```

**Note:** `httpx.AsyncClient` with `ASGITransport` is the standard pattern for testing FastAPI apps without spinning up a real server. This avoids the need for a live DB in unit tests of the health endpoint.

---

### `backend/tests/test_health.py` (test, request-response)

**Source:** RESEARCH.md Validation Architecture — INFRA-02 test

**Full file pattern:**
```python
import pytest

@pytest.mark.asyncio
async def test_health_returns_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

---

### `backend/pytest.ini` (config)

**Source:** RESEARCH.md Validation Architecture — Wave 0 Gaps

**Critical constraint:** `asyncio_mode = auto` — required by `pytest-asyncio` 1.3.0 to run async test functions without explicit `@pytest.mark.asyncio` decorators.

**Full file pattern:**
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

---

## Shared Patterns

### Async Session Factory
**Apply to:** `app/core/database.py`, `scripts/seed_demo.py`, `tests/conftest.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

`expire_on_commit=False` is mandatory everywhere — prevents `DetachedInstanceError` in background tasks that access ORM objects after commit.

### URL Scheme Split
**Apply to:** `alembic/alembic.ini`, `app/core/config.py`, `.env.example`

| User | URL scheme | Why |
|------|-----------|-----|
| FastAPI app engine | `postgresql+asyncpg://` | Async operations require asyncpg driver |
| Alembic migration runner | `postgresql://` | Alembic runner is synchronous; requires psycopg2 |

Never mix these two URLs. Using asyncpg in Alembic causes event loop errors.

### Empty `__init__.py` Files
**Apply to:** `app/__init__.py`, `app/core/__init__.py`, `app/models/__init__.py`, `app/schemas/__init__.py`, `app/api/__init__.py`

All are empty — standard Python package markers with no content.

### FastAPI Router Pattern
**Apply to:** `app/api/health.py`, `app/api/router.py`

Each endpoint module creates its own `router = APIRouter()` and defines routes on it. The aggregator `router.py` collects all sub-routers via `include_router()`. `main.py` calls `app.include_router(router)` exactly once.

---

## No Analog Found

All 22 files have no existing analog — this is a brand-new project with no application source code yet.

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| All 22 files listed above | various | various | Brand-new project; no existing source files |

---

## Key Gotchas (Cross-File)

These are RESEARCH.md pitfalls that affect multiple files. The planner must reference these in task actions:

| Pitfall | Files Affected | Prevention |
|---------|---------------|------------|
| Alembic autogenerate skips Vector columns | `0001_initial.py` | Hand-write only; never run `--autogenerate` |
| `@app.on_event("startup")` is deprecated | `main.py` | Use `lifespan` context manager exclusively |
| asyncpg URL in alembic.ini | `alembic.ini`, `env.py` | Use `postgresql://` (psycopg2) in alembic.ini |
| `expire_on_commit=True` default | `database.py`, `seed_demo.py` | Set `expire_on_commit=False` in all session factories |
| `postgres:16` Docker image | `docker-compose.yml` | Use `pgvector/pgvector:pg16` |
| `pydantic-settings` separate package | `requirements.txt`, `config.py` | Add `pydantic-settings` to requirements.txt explicitly |
| ivfflat index on empty table | `0001_initial.py` | Defer chunks.embedding ivfflat index; hnsw is safe on empty tables |

---

## Metadata

**Analog search scope:** Entire repository (`/Users/shrey/Desktop/swe projects/cortex/cortex/`)
**Files scanned:** .planning/ docs and CLAUDE.md only (no application source files exist)
**Pattern source:** `01-RESEARCH.md` exclusively
**Pattern extraction date:** 2026-04-25
