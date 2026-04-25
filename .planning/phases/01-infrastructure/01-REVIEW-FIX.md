---
phase: 01-infrastructure
fixed_at: 2026-04-25T00:00:00Z
review_path: .planning/phases/01-infrastructure/01-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 8
skipped: 0
status: all_fixed
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-04-25T00:00:00Z
**Source review:** .planning/phases/01-infrastructure/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 8 (CR-01, CR-02, CR-03, WR-01, WR-02, WR-03, WR-04, WR-05)
- Fixed: 8
- Skipped: 0

## Fixed Issues

### CR-01: Hardcoded credentials committed in alembic/alembic.ini

**Files modified:** `backend/alembic/alembic.ini`, `backend/alembic/env.py`
**Commit:** 0cafdcf
**Applied fix:** Replaced the literal `postgresql://cortex:cortex@localhost:5432/cortex` URL in `alembic.ini` with the placeholder `REPLACED_BY_ENV_PY`. Added `from app.core.config import settings` import to `env.py` and inserted `config.set_main_option("sqlalchemy.url", settings.database_url_sync)` before the migration functions so the URL is always read from the environment at runtime.

---

### CR-02: Settings() instantiated at module import time — crashes when env vars are absent

**Files modified:** `backend/app/core/config.py`
**Commit:** 3dc97da
**Applied fix:** Changed `openai_api_key: str` and `anthropic_api_key: str` to `openai_api_key: str | None = None` and `anthropic_api_key: str | None = None`. Both keys are unused in Phase 1 (needed only from Phase 3+ LLM extraction). This prevents `ValidationError` from aborting pytest collection in environments where those env vars are absent.

---

### CR-03: Engine created per-test with no cleanup on exception path — resource leak

**Files modified:** `backend/tests/conftest.py`, `backend/tests/test_migration.py`, `backend/tests/test_seed.py`
**Commit:** ed740a3
**Applied fix:** Added a module-scoped `db_engine` fixture to `conftest.py` that creates the engine once, yields it, and calls `await engine.dispose()` in teardown — guaranteed by pytest's fixture lifecycle even when test assertions raise. Rewrote `test_migration.py` and `test_seed.py` to accept `db_engine` as a parameter instead of each constructing their own engine and calling `dispose()` manually. This also covered WR-04 (see below).

---

### WR-01: Edge model has untyped, unguarded FK columns — referential integrity gap

**Files modified:** `backend/app/models/models.py`, `backend/alembic/versions/0001_initial.py`
**Commit:** 2357233
**Applied fix:** Added `ForeignKey("concepts.id", ondelete="CASCADE")` to both `from_id` and `to_id` columns in the `Edge` ORM model and the corresponding `op.create_table("edges", ...)` call in the initial migration. Edges in this system connect concept nodes, so binding both endpoints to `concepts.id` with cascade delete is the correct referential constraint.

---

### WR-02: Mapped[DateTime] type annotation is incorrect — should be Mapped[datetime]

**Files modified:** `backend/app/models/models.py`
**Commit:** ae1dc34
**Applied fix:** Added `from datetime import datetime` at the top of `models.py`. Replaced all 9 occurrences of `Mapped[DateTime]` with `Mapped[datetime]` across every model (`User`, `Course`, `Source`, `Chunk`, `Concept`, `ExtractionCache`, `Edge`, `Flashcard`, `Quiz`). The SQLAlchemy column type `DateTime` is retained as the `mapped_column(...)` argument; only the Python type annotation inside `Mapped[...]` was corrected.

---

### WR-03: test_health_returns_ok async test could become a no-op with bad pytest-asyncio version

**Files modified:** `backend/requirements.txt`
**Commit:** 8a16bbb
**Applied fix:** Pinned `pytest-asyncio` from the non-existent version `1.3.0` to `0.24.0` — the latest stable release that introduced `asyncio_mode = auto` support (added in 0.19). This ensures async test functions are properly awaited and not silently skipped as no-op coroutines.

---

### WR-04: conftest.py silently swallows ImportError — test misconfiguration is invisible

**Files modified:** `backend/tests/conftest.py`
**Commit:** ed740a3 (included in CR-03 commit)
**Applied fix:** Narrowed `except ImportError` to `except ModuleNotFoundError`. `ModuleNotFoundError` is the specific subclass that means the module does not exist yet (the intended use case). Any other `ImportError` subclass — such as the `ValidationError` raised by `Settings()` or a `SyntaxError` wrapped in an import error — will now propagate, making root-cause failures visible rather than silently swallowing them.

---

### WR-05: seed_demo.py does not handle database connection failure gracefully

**Files modified:** `backend/scripts/seed_demo.py`
**Commit:** 17ea92a
**Applied fix:** Wrapped the seed body in `try/except Exception/finally`. On any exception, prints a human-readable `"Seed failed — is the database running? Error: {exc}"` message to stderr and exits with code 1 instead of surfacing a raw asyncpg traceback. The `finally` block calls `await engine.dispose()` unconditionally, ensuring the connection pool is always cleaned up even when an exception interrupts the happy path before the original `dispose()` call.

---

## Skipped Issues

None — all 8 in-scope findings were successfully fixed.

---

_Fixed: 2026-04-25T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
