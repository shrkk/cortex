---
phase: 01-infrastructure
reviewed: 2026-04-25T00:00:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - backend/pytest.ini
  - backend/tests/conftest.py
  - backend/tests/test_health.py
  - backend/tests/test_migration.py
  - backend/tests/test_seed.py
  - backend/docker-compose.yml
  - backend/.env.example
  - backend/.gitignore
  - backend/requirements.txt
  - backend/app/core/config.py
  - backend/app/core/database.py
  - backend/app/models/models.py
  - backend/alembic/alembic.ini
  - backend/alembic/env.py
  - backend/alembic/versions/0001_initial.py
  - backend/app/main.py
  - backend/app/api/health.py
  - backend/app/api/router.py
  - backend/app/schemas/health.py
  - backend/scripts/seed_demo.py
findings:
  critical: 3
  warning: 5
  info: 3
  total: 11
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-04-25T00:00:00Z
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Reviewed the full Phase 1 infrastructure: FastAPI app bootstrap, SQLAlchemy models, Alembic migration, configuration, test suite, Docker Compose, and seed script. The skeleton is structurally sound and most design intent is clear. Three blockers were found: hardcoded credentials in `alembic.ini`, `Settings` crashing at import time when env vars are absent (breaking every test that imports `app`), and an engine resource leak in every migration/seed test. Several warnings address test reliability and schema/model drift.

---

## Critical Issues

### CR-01: Hardcoded credentials committed in `alembic/alembic.ini`

**File:** `backend/alembic/alembic.ini:8`
**Issue:** The `sqlalchemy.url` key is committed with the literal password `cortex:cortex@localhost`. Even though this is a dev credential, committing it to version control establishes a pattern that will carry forward to staging/production configs. It also means the URL cannot be overridden without editing a checked-in file, so CI running against a different host silently uses the wrong database. The `.env.example` correctly separates `DATABASE_URL_SYNC` — `alembic.ini` should follow the same pattern.
**Fix:** Remove the literal URL from `alembic.ini` and read it from the environment in `env.py` instead:

```python
# alembic/env.py — add at top of run_migrations_online / run_migrations_offline
import os
from app.core.config import settings

# Override whatever alembic.ini says
config.set_main_option("sqlalchemy.url", settings.database_url_sync)
```

Then change `alembic.ini` line 8 to a placeholder:

```ini
sqlalchemy.url = REPLACED_BY_ENV_PY
```

---

### CR-02: `Settings()` instantiated at module import time — crashes when env vars are absent

**File:** `backend/app/core/config.py:15`
**Issue:** `settings = Settings()` is a module-level statement. `Settings` declares `openai_api_key: str` and `anthropic_api_key: str` as **required** fields (no default). Any process that imports `app.core.config` — including pytest's collection phase — will raise a `ValidationError` and abort unless `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` are set. This makes the test suite environment-sensitive: `test_migration.py` and `test_seed.py` both import `settings` directly, and `conftest.py` imports `app.main` which transitively imports `settings`. CI without those keys will fail at collection, not at a meaningful test assertion.
**Fix:** Make the API keys optional with `None` defaults (they are unused in Phase 1):

```python
class Settings(BaseSettings):
    database_url: str
    database_url_sync: str
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    environment: str = "development"

    class Config:
        env_file = ".env"
```

Or keep them required but add them to `.env.example` with a note that they are required even for tests, and document that in pytest.ini / README.

---

### CR-03: Engine created per-test with no cleanup on exception path — resource leak

**File:** `backend/tests/test_migration.py:21-28`, `backend/tests/test_migration.py:31-39`, `backend/tests/test_migration.py:42-53`, `backend/tests/test_seed.py:8-19`
**Issue:** Each test creates a raw `create_async_engine(...)` and calls `await engine.dispose()` at the end. If any assertion or `await conn.execute(...)` raises an exception before `dispose()` is reached, the engine and its connection pool are never cleaned up. This causes connection leaks that exhaust the pool in the remaining tests, producing cryptic `asyncpg` timeout or connection-limit errors instead of a clear test failure.
**Fix:** Use a `try/finally` block or, better, a module-scoped fixture in `conftest.py`:

```python
# tests/conftest.py — add shared engine fixture
@pytest_asyncio.fixture(scope="module")
async def db_engine():
    engine = create_async_engine(settings.database_url)
    yield engine
    await engine.dispose()
```

Then each test accepts `db_engine` as a parameter instead of constructing its own.

---

## Warnings

### WR-01: `Edge` model has untyped, unguarded FK columns — referential integrity gap

**File:** `backend/app/models/models.py:146-148`
**Issue:** `from_id` and `to_id` are plain `Integer` columns with no `ForeignKey` constraint. The migration (`0001_initial.py:151-152`) matches this — no FK is defined there either. This means edges can reference non-existent node IDs with no database-level protection. Any cascade delete on `concepts` or other node tables will leave dangling edge rows silently. This is a schema correctness issue, not just a style concern.
**Fix:** If edges are intended to be polymorphic (pointing to concepts, quizzes, etc.), document that explicitly and add a check constraint or use a lookup table. If edges are expected to only connect `concepts`, add FK constraints to both columns:

```python
from_id: Mapped[int] = mapped_column(
    Integer, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
)
to_id: Mapped[int] = mapped_column(
    Integer, ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False
)
```

And update the migration accordingly.

---

### WR-02: `Mapped[DateTime]` type annotation is incorrect — should be `Mapped[datetime]`

**File:** `backend/app/models/models.py:14, 30, 57, 78, 101, 137, 151, 163, 181`
**Issue:** Every `created_at` column (and the `User.created_at` column) is annotated `Mapped[DateTime]` where `DateTime` is the SQLAlchemy column type class, not a Python type. The correct Python type for `Mapped[...]` is `datetime.datetime`. Using the SQLAlchemy type class here is tolerated by SQLAlchemy but is incorrect typing — static analysis tools (mypy, pyright) will not infer the correct Python type when reading these attributes. This affects all models: `User`, `Course`, `Source`, `Chunk`, `Concept`, `ExtractionCache`, `Edge`, `Flashcard`, `Quiz`.
**Fix:**

```python
from datetime import datetime
# Then annotate as:
created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

---

### WR-03: `test_health_returns_ok` is missing the `@pytest.mark.asyncio` decorator (or equivalent)

**File:** `backend/tests/test_health.py:4`
**Issue:** `pytest.ini` sets `asyncio_mode = auto`, which means pytest-asyncio will auto-mark async test functions. However, `pytest-asyncio==1.3.0` listed in `requirements.txt` is not a real published version — the latest stable release at the time of writing is `0.24.x`. If the installed version does not support `asyncio_mode = auto` in `pytest.ini`, all async tests silently become no-ops (they are collected as coroutines but never awaited, so assertions never run and the tests pass vacuously). This would mean the entire async test suite gives false green results.
**Fix:** Pin to an existing released version of `pytest-asyncio`:

```
pytest-asyncio==0.24.0
```

Verify `asyncio_mode = auto` is supported by that version (it was introduced in 0.19). If using an older version, add `@pytest.mark.asyncio` explicitly to each async test function.

---

### WR-04: `conftest.py` silently swallows `ImportError` — test misconfiguration is invisible

**File:** `backend/tests/conftest.py:16-18`
**Issue:** The bare `except ImportError: pass` block means if `app.main` fails to import for any reason other than a missing module (e.g., a `ValidationError` from `Settings()` as described in CR-02, or a syntax error in `app/api/router.py`), the `client` fixture is simply never defined. Tests that use `client` will then fail with `fixture 'client' not found` rather than showing the real import error. This makes debugging extremely difficult.
**Fix:** At minimum, narrow the exception to handle only the "module not yet created" scenario, or re-raise non-`ModuleNotFoundError` exceptions:

```python
try:
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    # ... fixture definition ...
except ModuleNotFoundError:
    pass  # app.main not yet created
```

`ImportError` is the base class — a `ModuleNotFoundError` is more specific and is the only case that should be silenced here.

---

### WR-05: `seed_demo.py` does not handle database connection failure gracefully

**File:** `backend/scripts/seed_demo.py:39-76`
**Issue:** If the database is not running when the script is executed (common on first `docker compose up` before the `db` container is healthy), the `create_async_engine` call succeeds (it is lazy) but the first `await session.execute(...)` raises a connection error that propagates as an unformatted asyncpg traceback. The script has no try/except and no human-readable error message directing the user to check the database. Combined with the fact that `engine.dispose()` is inside the `async with` block (it is called after the context manager exits), a connection failure will also skip `await engine.dispose()`.
**Fix:**

```python
async def seed() -> None:
    try:
        async with AsyncSessionLocal() as session:
            ...
    except Exception as exc:
        print(f"Seed failed — is the database running? Error: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        await engine.dispose()
```

---

## Info

### IN-01: `docker-compose.yml` exposes database port to all interfaces

**File:** `backend/docker-compose.yml:8`
**Issue:** `"5432:5432"` binds the PostgreSQL port on `0.0.0.0` (all interfaces). On a developer machine connected to a shared network, this exposes the database with the hardcoded `cortex/cortex` credentials to the local network. Prefer binding to `127.0.0.1` only.
**Fix:**
```yaml
ports:
  - "127.0.0.1:5432:5432"
```

---

### IN-02: `pytest.ini` is missing `filterwarnings` — deprecation noise will grow

**File:** `backend/pytest.ini`
**Issue:** SQLAlchemy 2.x, asyncpg, and pytest-asyncio all emit deprecation warnings during the test run. Without `filterwarnings`, these clutter output and can mask real warnings. Early addition is cheaper than retrofitting later.
**Fix:**
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
filterwarnings =
    error
    ignore::DeprecationWarning:sqlalchemy
    ignore::DeprecationWarning:asyncpg
```

---

### IN-03: `.gitignore` does not ignore `*.db` / local SQLite files or `alembic/versions/__pycache__`

**File:** `backend/.gitignore`
**Issue:** The gitignore covers Python bytecode and venv but omits `alembic/versions/__pycache__/` which will be created when alembic runs locally. It also does not ignore `.env.test` or similar patterns that developers commonly create. Minor but worth addressing before the first team commit.
**Fix:** Add to `.gitignore`:
```
alembic/versions/__pycache__/
.env.*
!.env.example
```

---

_Reviewed: 2026-04-25T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
