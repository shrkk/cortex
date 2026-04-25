---
phase: 2
plan: "02-01"
subsystem: backend/db
tags: [alembic, migration, pgvector, orm, schema]
dependency_graph:
  requires: []
  provides: [courses.embedding Vector(1536)]
  affects: [02-05-course-match-api, 02-06-ingest-endpoint]
tech_stack:
  added: []
  patterns: [hand-written-alembic-migration, pgvector-mapped-column]
key_files:
  created:
    - backend/alembic/versions/0002_course_embeddings.py
  modified:
    - backend/app/models/models.py
decisions:
  - "nullable=True on courses.embedding — existing rows have no embedding until seed backfill in Plan 02-05"
  - "No index on courses.embedding — table is tiny (<100 rows); sequential scan is fine"
  - "No op.execute CREATE EXTENSION — already done in 0001_initial.py"
metrics:
  duration: "~5 min"
  completed: "2026-04-25T23:30:24Z"
  tasks_completed: 2
  files_changed: 2
---

# Phase 2 Plan 01: Course Embeddings Migration Summary

**One-liner:** Hand-written Alembic migration adding `courses.embedding Vector(1536)` with matching ORM mapped_column, enabling cosine-similarity course matching for notch auto-assignment.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Create 0002_course_embeddings.py migration | c0de583 | backend/alembic/versions/0002_course_embeddings.py |
| 2 | Add embedding field to Course ORM model | c0de583 | backend/app/models/models.py |

## Verification Results

All success criteria met:

- `alembic upgrade head` ran clean on fresh DB (`docker compose down -v` cycle)
- `\d courses` in psql shows `embedding | vector(1536)` column
- `alembic downgrade -1` removed the column without error
- Re-upgrade after downgrade succeeded
- `Course.embedding` accessible in Python ORM without error
- `grep "embedding.*Vector(1536)" models.py` returns 3 matches (Chunk, Concept, Course)
- Exactly one `from pgvector.sqlalchemy import Vector` import in models.py

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — this plan is schema-only (migration + ORM mapping). No data, no API endpoints.

## Threat Flags

None — migration is a checked-in developer artifact with no user-input path. Both threats accepted per plan threat register (T-02-01-01, T-02-01-02).

## Self-Check: PASSED

- [x] `backend/alembic/versions/0002_course_embeddings.py` exists
- [x] `backend/app/models/models.py` modified (embedding field added to Course)
- [x] Commit c0de583 exists in git log
- [x] No unexpected file deletions in commit
- [x] SUMMARY.md created at correct path
