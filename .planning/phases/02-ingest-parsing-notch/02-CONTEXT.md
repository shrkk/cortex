# Phase 2: Ingest + Parsing + Notch - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Two interlinked surfaces delivered together:

1. **Swift notch app** — NotchDrop fork cloned into `notch/` within this repo; adds a `Cortex/` subfolder with 4 new Swift files + one surgical edit to the existing drop handler. Handles drag-and-drop ingest, course assignment UI (CortexCourseTab), status pill, and settings panel.

2. **Backend ingest pipeline** — `POST /ingest` returns `{source_id, status: "pending"}` immediately; a background task executes all 8 pipeline stages (Phase 2 implements parse → chunk → embed; Phases 3 and 4 fill in extract → resolve → edges → flashcards → signals as stubs). `GET /courses/match` provides confidence-scored course assignment via embedding similarity.

Phase 2 is complete when: a PDF dragged into the notch creates a `sources` row with status=processing (pipeline in-flight) or status=done (if pipeline completes fast), chunks are created and embedded, and the status pill confirms delivery.

</domain>

<decisions>
## Implementation Decisions

### Background Pipeline Architecture

- **D-01:** One continuous background task function wires all 8 stages (`parse → chunk → embed → extract → resolve → edges → flashcards → signals`). Phase 2 implements the first 3 stages; Phases 3–4 add real implementations for the stubs. The stub stages are no-ops that return immediately.
- **D-02:** `status=processing` throughout execution; `status=done` only after the final stage completes. No intermediate status values (no `chunked`, `embedded`, etc.).
- **D-03:** Error handling: first exception in any stage sets `status=error` and writes the full traceback to `sources.error`. No automatic retries — developer reads the error and reruns manually with `force=true`.
- **D-04:** `force=true` query param bypasses source-level `content_hash` deduplication only. The `extraction_cache` table is still consulted to avoid redundant LLM calls.

### Course Matching (`GET /courses/match`)

- **D-05:** Confidence algorithm: embed the hint text with `text-embedding-3-small`; cosine-compare against stored `courses.embedding` values. Most accurate for fuzzy course name matching (e.g., filename "cs229_lecture.pdf" → "CS 229: Machine Learning").
- **D-06:** Requires a new Alembic migration (hand-written) adding `embedding Vector(1536)` to the `courses` table. The migration adds the column as nullable; the Phase 2 seed script backfills embeddings for existing seed courses so `/courses/match` works on a migrated DB without re-seeding.
- **D-07:** When confidence < 0.65 (or no courses exist), return `null`. The Swift app sees `null` → shows the full CortexCourseTab picker. No top-candidate is returned alongside — `null` means "user must choose."

### PDF Chunking Strategy

- **D-08:** Strict page-per-chunk as specified in PARSE-01. One `Chunk` row per PDF page; `page_num` set in metadata. No token-based size cap — dense pages stay whole.
- **D-09:** Empty/near-empty pages (< 50 characters after whitespace normalization) are skipped — no chunk created, no embedding call. Avoids wasting embedding tokens on title pages, blank separators, and page-number-only pages.
- **D-10:** Image OCR (PARSE-02): Claude vision output stored verbatim as `chunk.text` — raw markdown including diagram descriptions, LaTeX equations, and prose. No post-processing.

### NotchDrop Fork

- **D-11:** Fork cloned into `notch/` subdirectory of this repo (alongside `backend/`). One git history, notch-specialist agent works within the same worktree.
- **D-12:** Cortex Swift module + surgical edit to the existing NotchDrop drop handler are implemented in one plan by the notch-specialist agent. Both touch the same Xcode project; separating them adds overhead with no benefit.
- **D-13:** Default backend URL stored in `UserDefaults`: `http://localhost:8000`. User can override in CortexSettings panel.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Requirements
- `.planning/REQUIREMENTS.md` — Full requirement list; Phase 2 requirements are ING-01 through ING-15, PARSE-01 through PARSE-05, PIPE-01 through PIPE-07
- `.planning/PROJECT.md` — Locked decisions, critical pitfalls, tech stack constraints, NotchDrop fork context

### Phase 2 Roadmap Details
- `.planning/ROADMAP.md` § "Phase 2: Ingest + Parsing + Notch" — Goal, success criteria, and stack notes (UTI ordering, BackgroundTasks pattern, session-per-stage, force param, CORTEX_ENABLED guard, UserDefaults session default)

### Existing Backend Code (Phase 1 output)
- `backend/app/models/models.py` — All ORM models; `Source`, `Chunk`, `Course`, `ExtractionCache` are the primary tables for Phase 2
- `backend/app/main.py` — FastAPI app with lifespan hook (startup reconciliation already implemented), CORS already configured
- `backend/app/core/database.py` — `AsyncSessionLocal` and `engine` for the session-per-stage pattern
- `backend/app/core/config.py` — Settings (env vars, DB URL pattern)

### Existing Migration
- `backend/alembic/versions/0001_initial.py` — Reference for hand-written migration style; Phase 2 adds `0002_course_embeddings.py` for the `courses.embedding` column

### NotchDrop Reference
- `notch/` — To be created by cloning the Lakr233/NotchDrop fork; `NotchDrop/NotchDrop/Cortex/` is where the 4 new Swift files live

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/core/database.py` → `AsyncSessionLocal`: the session factory used in every pipeline stage (fresh `async with AsyncSessionLocal() as session:` per stage, per ROADMAP stack notes)
- `backend/app/models/models.py` → `Source`, `Chunk`, `Course`, `ExtractionCache`: all tables Phase 2 writes to are already defined and migrated
- `backend/app/main.py` → `lifespan` function: startup reconciliation (`processing` → `pending`) already implemented; CORS middleware already configured

### Established Patterns
- **Session-per-stage**: each pipeline stage opens and commits its own `AsyncSessionLocal` session — do NOT pass a single session through all 8 stages (connection pool exhaustion)
- **Hand-written Alembic migrations**: `0001_initial.py` shows the pattern; `0002_course_embeddings.py` must follow the same format; test on `docker compose down -v && docker compose up -d && alembic upgrade head`
- **`source_metadata` / `edge_metadata` attribute names**: SQLAlchemy reserves `metadata`; `mapped_column("metadata", JSON)` preserves the DB column name
- **`BackgroundTasks` pattern**: add the pipeline call via FastAPI's `background_tasks.add_task(run_pipeline, source_id)` inside the route; do NOT `await` it inline

### Integration Points
- `POST /ingest` → creates `Source` row, enqueues background task, returns `{source_id, status: "pending"}`
- Background task → writes `Chunk` rows (one per non-empty PDF page), calls OpenAI embeddings API, stores `chunk.embedding`
- `GET /courses/match` → queries `courses` table with cosine similarity on `courses.embedding`; needs the `0002` migration to exist
- `courses.embedding` backfill → seed script embeds existing course titles via OpenAI API on startup

</code_context>

<specifics>
## Specific Ideas

- The ROADMAP stack notes call out `NSItemProvider` UTI ordering explicitly: check `public.png` / `public.jpeg` BEFORE `public.file-url` to avoid temp-file URLs from browser image drags disappearing before the upload completes. This is a known pitfall and must be in the Swift implementation.
- The `#if CORTEX_ENABLED` compile-time guard in the drop handler surgical edit is required — preserves fallback behavior and keeps the diff minimal.
- Session default (ING-15): last-selected course ID stored in `UserDefaults` key `cortex.lastCourseId`; pre-fills CortexCourseTab on next drop within the same session.
- arXiv URL rewriting (PARSE-04): detect `arxiv.org/abs/` pattern and rewrite to `arxiv.org/pdf/` before routing to the PDF parser. Only `abs/` links — all other URLs go through trafilatura.

</specifics>

<deferred>
## Deferred Ideas

- Retry logic for LLM and HTTP calls (e.g., exponential backoff on rate limits) — decided against for Phase 2; can be added in Phase 3 or 4 if needed
- Returning the top candidate course with a low-confidence flag — deferred; Phase 2 uses null-means-choose contract. Could be a v2 UX enhancement.
- Token-based chunk splitting (cap at 800 tokens) — deferred; page-per-chunk is sufficient for Phase 2 and 3; revisit if extraction quality suffers on dense lecture PDFs

</deferred>

---

*Phase: 2-Ingest + Parsing + Notch*
*Context gathered: 2026-04-25*
