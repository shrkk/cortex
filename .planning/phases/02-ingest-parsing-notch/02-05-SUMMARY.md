---
phase: 2
plan: "02-05"
subsystem: backend/ingest+pipeline
tags: [ingest, pipeline, fastapi, openai, pgvector, dedup, ssrf, tdd]
dependency_graph:
  requires:
    - "02-01"  # courses.embedding migration for course backfill
    - "02-02"  # parsers.py (parse_pdf, parse_url, parse_image, parse_text)
    - "02-03"  # courses API (course_id FK exists in sources table)
  provides:
    - "POST /ingest"
    - "run_pipeline"
    - "IngestResponse schema"
    - "backfill_course_embeddings"
  affects:
    - "02-06"  # notch app calls POST /ingest
    - "02-07"  # future phases use pipeline stages
    - "02-08"  # seed script uses backfill
tech_stack:
  added:
    - "AsyncOpenAI embeddings.create — text-embedding-3-small 1536-dim batch embedding"
    - "hashlib sha256 — content deduplication (PIPE-03)"
    - "ipaddress stdlib — SSRF protection via private network check"
    - "base64 stdlib — PDF/image bytes stored as base64 in Text column"
  patterns:
    - "Session-per-stage: each pipeline stage opens its own AsyncSessionLocal"
    - "BackgroundTasks.add_task — endpoint returns 202 before pipeline runs"
    - "_DuplicateContent sentinel exception — exits pipeline early without setting error status"
    - "TDD RED/GREEN for both pipeline.py and ingest.py"
key_files:
  created:
    - "backend/app/schemas/ingest.py"
    - "backend/app/pipeline/pipeline.py"
    - "backend/app/api/ingest.py"
    - "backend/tests/test_pipeline.py"
    - "backend/tests/test_ingest.py"
  modified:
    - "backend/app/api/router.py"
    - "backend/scripts/seed_demo.py"
decisions:
  - "_DuplicateContent caught before generic Exception in run_pipeline — duplicate ingest marks status=done not status=error"
  - "PDF/image file bytes stored as base64 in source.raw_text (Text column); decoded in pipeline parse stage"
  - "Two AsyncSessionLocal blocks in _stage_parse_and_chunk: first for dedup+hash, second for parse+chunk creation (clean separation)"
  - "backfill_course_embeddings wrapped in try/except — graceful on API 401/timeout; seed exits 0 regardless"
  - "force=True forwarded through entire call chain: /ingest query param → background task → _stage_parse_and_chunk"
metrics:
  duration: "~10 minutes"
  completed_date: "2026-04-25T23:47:00Z"
  tasks_completed: 4
  tasks_total: 4
  tests_added: 31
  tests_passing: 31
---

# Phase 2 Plan 05: Ingest Endpoint + Pipeline Summary

**One-liner:** FastAPI POST /ingest (multipart + JSON) with 8-stage background pipeline implementing parse/chunk/embed as real stages, sha256 content dedup with force bypass, SSRF protection on URL ingest, and course embedding backfill in seed script.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create ingest Pydantic schemas | a68d1d4 | backend/app/schemas/ingest.py |
| 2 (RED) | Add failing pipeline tests | 038bbb8 | backend/tests/test_pipeline.py |
| 2 (GREEN) | Implement pipeline.py | 845c392 | backend/app/pipeline/pipeline.py |
| 3 (RED) | Add failing ingest endpoint tests | 3aee69a | backend/tests/test_ingest.py |
| 3 (GREEN) | Implement ingest.py + wire router | cab4c96 | backend/app/api/ingest.py, backend/app/api/router.py |
| 4 | Add backfill_course_embeddings to seed | 7ad70ef | backend/scripts/seed_demo.py |

## What Was Built

### POST /ingest endpoint (`backend/app/api/ingest.py`)

Two content type paths:
- **multipart/form-data**: fields `course_id` (int), `kind` (pdf|image), `file` (UploadFile). File bytes read, base64-encoded, stored in `source.raw_text`. 50MB cap enforced before read (413 on excess).
- **application/json**: `{course_id, kind: "url", url}` or `{course_id, kind: "text", title?, text}`. URL path runs SSRF check before DB insert.

**SSRF protection** (`_is_safe_url`):
- Blocks non-http/https schemes
- Resolves hostname via `socket.getaddrinfo` and checks all returned IPs against private/loopback ranges: 127.x, 10.x, 172.16.x, 192.168.x, 169.254.x, ::1, fc00::/7
- Fail-closed: DNS resolution errors return False

**Response**: `{source_id: N, status: "pending"}` with 202. Pipeline enqueued via `BackgroundTasks.add_task` — endpoint returns before any pipeline work.

**`force=True` query param** (D-04): forwarded to `run_pipeline`, which forwards to `_stage_parse_and_chunk`, bypassing the sha256 content_hash dedup check.

### 8-Stage Background Pipeline (`backend/app/pipeline/pipeline.py`)

**Real stages (Phase 2):**
- **Stage 1** `_stage_set_processing`: sets `source.status = "processing"`
- **Stage 2** `_stage_parse_and_chunk`: computes sha256 content_hash; dedup check (skip if force=True); calls appropriate parser (parse_pdf/parse_url/parse_image/parse_text); creates Chunk rows
- **Stage 3** `_stage_embed`: batch-embeds all un-embedded chunks via `text-embedding-3-small` (1536 dims); skips if OPENAI_API_KEY not set

**No-op stubs (Phase 3/4):**
- `_stage_extract_stub`, `_stage_resolve_stub`, `_stage_edges_stub`, `_stage_flashcards_stub`, `_stage_signals_stub`

**Error handling:**
- `_DuplicateContent`: caught before generic `except Exception` — sets `status=done`, writes `source_metadata={"duplicate_of": existing_id}`, does NOT set status=error
- All other exceptions: caught by generic handler, sets `status=error`, writes `traceback.format_exc()[:4000]` to `source.error`

**Session-per-stage** (critical): 6 separate `async with AsyncSessionLocal()` blocks — one per DB-touching stage. Never passes sessions across stage boundaries.

### Ingest Schemas (`backend/app/schemas/ingest.py`)

- `IngestResponse(source_id, status)` — response model for 202
- `IngestURLBody(course_id, kind="url", url)` — JSON URL ingest shape
- `IngestTextBody(course_id, kind="text", title?, text)` — JSON text ingest shape

### Course Embedding Backfill (`backend/scripts/seed_demo.py`)

`backfill_course_embeddings(session)`:
- Finds courses with `embedding IS NULL`
- Batch-embeds titles via `text-embedding-3-small`
- Gracefully skips if `OPENAI_API_KEY` absent or returns API error (seed exits 0)
- Called from `seed()` after course rows committed, using a fresh `AsyncSessionLocal` session

## TDD Gate Compliance

| Plan | Gate | Commit | Status |
|------|------|--------|--------|
| Task 2 (pipeline) | RED (test) | 038bbb8 | PASS — 13 tests failed: ModuleNotFoundError |
| Task 2 (pipeline) | GREEN (feat) | 845c392 | PASS — 13 tests passing |
| Task 3 (ingest) | RED (test) | 3aee69a | PASS — 18 tests failed: ModuleNotFoundError |
| Task 3 (ingest) | GREEN (feat) | cab4c96 | PASS — 18 tests passing |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Error Handling] backfill_course_embeddings graceful on API 401**

- **Found during:** Task 4 verification (`python scripts/seed_demo.py`)
- **Issue:** `backend/.env` contains `OPENAI_API_KEY=sk-placeholder` (non-empty string). The plan's `backfill_course_embeddings` only guards against absent key (`not settings.openai_api_key`). With a placeholder key, the OpenAI call is made, receives 401, and propagates up to `seed()` which calls `sys.exit(1)`. Acceptance criteria requires exit 0.
- **Fix:** Added `try/except Exception` around the `client.embeddings.create` call. On failure, prints a warning and returns early (courses seeded without embeddings). `seed()` continues to exit 0.
- **Files modified:** `backend/scripts/seed_demo.py`
- **Commit:** 7ad70ef

## Known Stubs

The following pipeline stages are intentional no-ops in Phase 2:
- `_stage_extract_stub` — Phase 3 will implement LLM concept extraction with extraction_cache check
- `_stage_resolve_stub` — Phase 3 will implement cosine similarity concept resolution (0.92/0.80 thresholds)
- `_stage_edges_stub` — Phase 3 will create co-occurrence and prerequisite edges
- `_stage_flashcards_stub` — Phase 4 will generate 3-6 flashcard nodes per concept
- `_stage_signals_stub` — Phase 4 will detect struggle signals

These stubs are expected per plan — they do not prevent the plan goal (parse/chunk/embed pipeline) from being achieved.

## Threat Flags

No new trust boundaries introduced beyond what was modeled in the plan's STRIDE register. All mitigations applied:

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-02-05-01 | 50MB limit enforced; pymupdf exceptions caught in pipeline try/except |
| T-02-05-02 | `_is_safe_url()` blocks all 7 private/loopback ranges; fail-closed on DNS error |
| T-02-05-03 | `MAX_UPLOAD_BYTES = 50MB`; checked before `upload.read()` |
| T-02-05-04 | httpx timeout=10s enforced in `parse_url` (parsers.py, Plan 02-02) |
| T-02-05-05 | OPENAI_API_KEY from `settings`; never logged; not in error responses |
| T-02-05-07 | kind validated: multipart only accepts pdf/image; JSON only url/text; unsupported → 400 |

## Self-Check

- [x] `backend/app/schemas/ingest.py` exists
- [x] `backend/app/pipeline/pipeline.py` exists
- [x] `backend/app/api/ingest.py` exists
- [x] `backend/app/api/router.py` modified (ingest.router wired)
- [x] `backend/scripts/seed_demo.py` modified (backfill_course_embeddings added)
- [x] `backend/tests/test_pipeline.py` exists (13 tests)
- [x] `backend/tests/test_ingest.py` exists (18 tests)
- [x] Commit a68d1d4 exists
- [x] Commit 038bbb8 exists
- [x] Commit 845c392 exists
- [x] Commit 3aee69a exists
- [x] Commit cab4c96 exists
- [x] Commit 7ad70ef exists
- [x] 31/31 new tests passing

## Self-Check: PASSED
