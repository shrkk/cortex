# Project Research Summary

**Project:** Cortex (student knowledge-graph + spaced-repetition second-brain)
**Domain:** Knowledge graph + LLM extraction pipeline + SRS — macOS notch drop zone, FastAPI, pgvector, React Flow
**Researched:** 2026-04-25
**Confidence:** HIGH (stack and pitfall findings are well-grounded; architecture patterns verified against official docs)

---

## Executive Summary

Cortex sits at the intersection of three well-understood domains — ingestion pipelines, knowledge graph visualization, and spaced-repetition review — but combines all three in a way no existing product does. The recommended build approach is a single-process FastAPI backend with BackgroundTasks for the extraction pipeline, pgvector in Postgres for vector similarity, and a Next.js 14 App Router frontend with React Flow for graph rendering. The spec's stack is coherent and correct for hackathon scope; the only meaningful deviations research recommends are switching the pgvector index from ivfflat to hnsw (to avoid the index-on-empty-table recall collapse), using `@xyflow/react` as the React Flow package name (not `reactflow`), and using `@dagrejs/dagre` as the layout library (not the abandoned `dagre`). These are not architectural changes — they are package-name and index-type substitutions that, if missed, cause silent failures that are hard to diagnose under time pressure.

The most dangerous category of risk is silent failure: the NSItemProvider UTI ordering bug causes drops to silently create dead-URL source rows; an ivfflat index built on an empty table silently degrades recall; a missing CORS `allow_origins=["*"]` causes Swift URLSession drops to silently never arrive at the backend; and a one-session-per-pipeline-run pattern silently exhausts the connection pool after seeding. Every one of these produces a symptom that looks like "the feature doesn't work" rather than a clear error. The mitigations are simple but must be applied before, not after, the first end-to-end test.

The demo is won or lost in three moments: (1) the live PDF drop creating visible graph nodes within ~60 seconds, (2) the graph lighting up with red/pulsing nodes after seeded reviews, and (3) the weak-spots quiz button producing a targeted 7–10 question set against recognizable concept names. Research identifies the seed data mastery variance as the most commonly overlooked demo-prep step — if all mastery scores are seeded at 0.5, the weak-spots quiz looks random, and the demo's killer feature is unconvincing.

---

## Key Findings

### Stack — Deviations from Spec and Critical Pins

The spec's stack is validated. Three substitutions are required and one is strongly recommended:

**Required substitutions:**
- **`@xyflow/react` (not `reactflow`)** — React Flow v12 renamed the npm package. The old `reactflow` package is a deprecated alias. Import from `@xyflow/react ^12.0.0`.
- **`@dagrejs/dagre` (not `dagre`)** — The original `dagre` package has been unmaintained since ~2018. The `@dagrejs/dagre` fork is the actively maintained replacement with TypeScript types. Using the original `dagre` with `@xyflow/react` v12's ESM build causes `dagre.layout is not a function` at runtime.
- **`pgvector/pgvector:pg16` Docker image (not `postgres:16`)** — The base `postgres:16` image requires manual pgvector extension installation via init script, which fails silently in some Compose setups. The official `pgvector/pgvector:pg16` image has pgvector pre-built.

**Strongly recommended substitution:**
- **hnsw index (not ivfflat) for the concepts table** — ivfflat requires a training phase against existing data. An ivfflat index built at migration time on an empty table has near-zero recall until `REINDEX` after data load. hnsw works correctly on an empty table and as rows insert incrementally, which matches Cortex's pipeline (concepts are inserted one at a time during extraction). For the chunks table, ivfflat is acceptable but must be created after seed data is loaded, not in the initial migration.

**Core technologies confirmed correct:**
- FastAPI `>=0.111,<0.116` + `uvicorn[standard]` — correct async patterns; use `BackgroundTasks` for pipeline
- SQLAlchemy 2.0 + Alembic 1.13 — use `AsyncSession` throughout; `async_sessionmaker` for background tasks
- `asyncpg>=0.29.0` (async driver) + `psycopg2-binary` (Alembic sync migrations only)
- `anthropic>=0.25.0` — use tool_use (structured output) for all JSON extraction; never parse free-text JSON with regex
- `openai>=1.30.0` — use the v1.x client; define a single `EMBEDDING_MODEL = "text-embedding-3-small"` constant module-wide
- `pymupdf>=1.24.0` — import as `fitz` (canonical); do not mix `import fitz` and `import pymupdf` in the same file
- `trafilatura>=1.6.0` — good for article pages; returns None/empty for SPAs; add a 200-char length check with BeautifulSoup fallback
- Next.js 14.2.x — do NOT upgrade to 15 mid-hackathon; v15 changed caching defaults and server action behavior
- SM-2 algorithm: clamp `ease_factor >= 1.3`, use grade mapping 1=Again/3=Hard/4=Good/5=Easy, store all timestamps as UTC

**Full installation reference:** See `.planning/research/STACK.md` for pinned `requirements.txt` and `package.json` entries.

---

### Features — What Is Demo-Critical vs. Deferrable

The spec is well-constructed. No critical table-stakes features are missing. The gap analysis found four minor omissions worth closing:

**Demo-critical (must work on demo day):**
- Notch drop (PDF + URL) — this IS the demo opener; no other product does drag-into-notch-to-graph
- Auto-generated concept graph with mastery coloring (red/yellow/green) + pulsing struggle dots
- SRS review session with Again/Hard/Good/Easy buttons (not numbers — the UI label mapping matters)
- Weak-spots quiz button — the "killer button"; only works impressively if mastery variance is real in seed data
- Node detail panel with gotchas — makes the panel feel like a tutor, not a filing cabinet
- Dashboard with cards-due-today count — students need this before starting a session

**Should-have (adds polish, not demo-breaking if rough):**
- Clipboard ingestion (`⌘V`) — secondary to drag; requires notch to be key window first
- Image ingestion + Claude OCR — if cut, URL + PDF still demo cleanly
- Library page source list — students need this to verify ingestion worked

**Defer (v2+):**
- Per-grade interval preview under grade buttons (Anki-style "Again: 10min | Good: 4d") — high-value polish but not demo-critical
- Pre-quiz concept list shown before quiz starts
- Mastery delta display post-quiz ("Gradient Descent: 0.3 → 0.6")
- Undo last card grade

**Four spec gaps to address explicitly:**
1. Empty-queue state on Study page — when `GET /flashcards/due` returns empty, show "All caught up! Next review: [timestamp]" not a blank page
2. Grade button labels — specify "Again / Hard / Good / Easy" in the UI spec; do not show grade numbers or invent new labels
3. Partial-concept UI state — if a concept has no summary yet (pipeline still running), node panel must show a loading/pending state
4. Empty dashboard state — "Create your first course to get started" when no courses exist

---

### Architecture — Build Order and Component Boundaries

The spec's build order is architecturally correct. The key dependency chain is hard:

```
Phase 0 (DB schema) → Phase 2 (ingest skeleton) → Phase 1 (full pipeline)
                                                          |
                          Phase 3 (graph API) ← concepts + edges written
                          Phase 4 (SRS)       ← flashcards written
                          Phase 5 (quiz)      ← mastery written
                               |
                          Phase 7 (frontend)  ← APIs stable
                          Phase 8 (Swift)     ← POST /ingest stable
                               |
                          Phase 9 (seed data) ← full backend complete
                          Phase 6/10 (polish/demo)
```

**Five anti-patterns confirmed by architecture research:**

1. **One SQLAlchemy session per pipeline run** — opens a session at pipeline start and passes it through all 8 stages. A 60-second pipeline with one session holds a connection pool slot for the full duration. Connection pool exhausts after seeding. Fix: open a fresh `async with AsyncSession(engine) as session:` inside each stage function.

2. **ivfflat index in the initial Alembic migration** — index built on an empty table is useless. Fix: create it in a separate migration that runs after `seed_demo.py`, or add `REINDEX` at the end of the seed script.

3. **`import dagre from 'dagre'`** — the original `dagre` package's default export is incompatible with ESM. Fix: `import * as dagre from '@dagrejs/dagre'`.

4. **No course_id filter in the ANN resolver query** — "Gradient Descent" in a CS course merges with "Gradient Descent" in a Biology course. Fix: always include `AND course_id = :course_id` in the resolver's cosine similarity query.

5. **Calling `CortexDropHandler` without a `#if CORTEX_ENABLED` compile-time guard** — runtime toggle alone doesn't restore original NotchDrop file-shelf behavior. Fix: wrap the structural edit in `#if CORTEX_ENABLED / #endif`.

**FastAPI BackgroundTasks verdict:** Sufficient for hackathon scope. On startup, mark any `status NOT IN ('done','error','pending')` rows as `status=error` with message "server restart — use retry". Add `POST /sources/{id}/retry` endpoint. This gives a clean recovery story without Celery or Redis.

**Concept resolution thresholds (0.92/0.80):** Reasonable starting points. After Phase 4, inspect the concept table manually. If distinct concepts are merging (e.g., "Gradient Descent" and "Stochastic Gradient Descent" at ~0.94), raise to 0.95. If trivial duplicates are not merging, lower to 0.90. The extraction prompt must instruct the model to return full canonical names, never abbreviations — "NN" vs "Neural Network" can score below 0.92, creating duplicate nodes.

---

### Critical Pitfalls — Top 6 to Prevent

These are ranked by the combination of severity and probability of hitting them during a hackathon build:

**1. NSItemProvider UTI ordering — file URL shadows image data (C-1)**
Drag an image from a browser; the handler picks the temp `file://` URL instead of the image bytes; the temp file disappears seconds after drop; the backend gets a 404. Prevention: check `public.png / public.jpeg / public.tiff` BEFORE `public.file-url`. Log all advertised UTI types at debug level during Phase 1 development.

**2. BackgroundTasks silent loss on server restart (C-4)**
Frequent `uvicorn --reload` during development kills in-flight extraction tasks with no error. Source rows stick at `status=processing` forever. Seed script appears to succeed but produces empty concept graphs. Prevention: startup reconciliation that resets stuck rows to `status=error`; add `POST /sources/{id}/retry`.

**3. React Flow v12 dagre — all nodes at origin (C-10)**
Using a v11-era dagre example with the v12 API: layout runs without error but positions are never applied to React Flow node state; every node renders at `{x:0, y:0}` as a pile. Prevention: copy the official xyflow.com v12 dagre example verbatim as the starting point; define `nodeTypes` outside the component body; call `setTimeout(() => reactFlowInstance.fitView(), 0)` after `setNodes(layoutedNodes)`.

**4. Alembic autogenerate skips pgvector Vector columns (C-6)**
`alembic revision --autogenerate` does not understand `pgvector.sqlalchemy.Vector`. It either generates a spurious ALTER or skips the column entirely. The migration runs without error but `embedding` columns are missing in the fresh DB. Prevention: write the initial migration manually; include `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` before table creation; test on `docker compose down -v && docker compose up -d` before Phase 3.

**5. SQLAlchemy session leak in BackgroundTask — connection pool exhaustion (C-5)**
Passing a request-scope session into a background task, or not scoping sessions per stage, causes connections to be held open for the duration of a 60-second pipeline. After seeding, the API hangs indefinitely. Prevention: open a fresh `async with AsyncSession(engine) as session:` inside every stage function; set `pool_size=10, max_overflow=5, pool_pre_ping=True` on the engine.

**6. CORS missing-Origin blocks Swift URLSession drops (m-3)**
FastAPI CORSMiddleware with `allow_origins=["http://localhost:3000"]` does not allow requests with no `Origin` header. Swift's `URLSession` sends no `Origin` header. All drops from the notch app silently fail. Prevention: `allow_origins=["*"]` for local development is correct and sufficient; document it.

**Three additional moderate-severity pitfalls:**
- Claude concept extraction hallucination (C-9) — use `tool_use` with strict JSON Schema and `additionalProperties: false`; add negative prompt instruction "Do not extract generic study skills or acronym-only concepts"; manually inspect 10 concept nodes after Phase 4
- Embedding dimension mismatch (C-8) — define `EMBEDDING_MODEL = "text-embedding-3-small"` and `EMBEDDING_DIM = 1536` as module-level constants; assert `len(embedding) == EMBEDDING_DIM` before every insert
- Seed mastery variance absent (M-5) — if all mastery scores are seeded at 0.5, the weak-spots quiz looks random; seed ~25% at 0.2–0.4, ~50% at 0.45–0.65, ~25% at 0.7–0.9; name the weak-spot concepts memorably ("Kernel Trick", "Vanishing Gradient")

---

## Implications for Roadmap

### Phase 0: Infrastructure Foundation
**Rationale:** Everything depends on Postgres being up and the schema being correct. Must be first.
**Delivers:** Docker Compose with `pgvector/pgvector:pg16`, Alembic migration with manually written Vector columns (not autogenerate), `CREATE EXTENSION IF NOT EXISTS vector` in migration, hnsw index on concepts (empty-table safe), ivfflat index on chunks deferred to post-seed migration.
**Watch out for:** C-6 (Alembic autogenerate skipping Vector columns) — write this migration by hand and test on a clean DB.

### Phase 1: NotchDrop Fork (Cortex Swift Module)
**Rationale:** The notch drop is the demo opener. Getting it working early validates the end-to-end path and surfaces UTI/pasteboard issues before they become late-stage blockers.
**Delivers:** `Cortex/` subfolder with 4 Swift files, single surgical edit to tray drop handler behind `#if CORTEX_ENABLED`, status pill (Sending → Sent → Error), UTI priority ordering (image before file-url), macOS Accessibility permission check at startup.
**Watch out for:** C-1 (UTI ordering), C-2 (NSEvent global monitor scope), C-3 (Safari vs Chrome pasteboard types), m-2 (Accessibility permissions), m-3 (CORS missing-Origin — configure `allow_origins=["*"]` before testing drops).

### Phase 2: Ingest Endpoint + Pipeline Skeleton
**Rationale:** Establishes the BackgroundTasks pattern and session-per-stage discipline before any service logic is built in. Getting this wrong cascades into every phase that follows.
**Delivers:** `POST /ingest` returning `{source_id, status: 'pending'}` immediately, 8-stage FSM skeleton writing status at each transition, startup reconciliation hook, `POST /sources/{id}/retry` endpoint, `force=true` query parameter for development re-ingestion, CORS configured correctly.
**Watch out for:** C-4 (BackgroundTask shutdown loss), C-5 (session leak), m-3 (CORS).

### Phase 3: Parsing + Embedding Pipeline
**Rationale:** The parser and embedder are the first two stages with real complexity. Validating them in isolation before concept extraction reduces debugging surface.
**Delivers:** PDF parser (pymupdf/fitz), URL parser (httpx + trafilatura with 200-char fallback to BeautifulSoup), image parser (Claude vision), chunk embedding (text-embedding-3-small, batched), `EMBEDDING_MODEL` and `EMBEDDING_DIM` module-level constants, `Vector(1536)` column dimension enforcement.
**Watch out for:** C-8 (dimension mismatch — define constants now, not later), m-1 (trafilatura SPA empty return).

### Phase 4: Concept Extraction + Resolution + Edges + Flashcard Generation
**Rationale:** The pipeline centerpiece. Most LLM-touching logic lives here. The longest phase by implementation time.
**Delivers:** Claude concept extractor using `tool_use` with strict JSON Schema, extraction_cache keyed on `(chunk_hash, model_version)`, concept resolver with course-scoped ANN query (hnsw for concepts, 0.92/0.80 thresholds), LLM tiebreaker for ambiguous pairs, edge creation (co-occurrence + prerequisite + contains), flashcard generation (3–6 cards per concept, 4 types), mastery initialization at 0.5, BFS depth calculation.
**Watch out for:** C-9 (Claude JSON failures + hallucinated concepts — use tool_use, inspect 10 nodes manually after seeding), M-1 (threshold tuning — inspect concept table, adjust if over/under-merging), M-2 (extraction_cache not invalidating on prompt change — TRUNCATE cache after every prompt edit during development). This phase requires manual DB inspection before moving on.

### Phase 5: Graph API + SRS Endpoints
**Rationale:** Both APIs are consumed by the frontend in Phase 7. Getting their contracts stable before frontend work avoids rework.
**Delivers:** `GET /courses/{id}/graph` serializing nodes with mastery/struggle fields, `GET /flashcards/due`, `POST /flashcards/{id}/review` (SM-2 update), mastery score update on review, struggle signal computation. SM-2 implementation with `ease_factor >= 1.3` clamp, UTC timestamps throughout, grade labels mapped to Again/Hard/Good/Easy in API docs.
**Watch out for:** M-4 (SM-2 ease_factor floor — include a unit test for "grade 1 ten times in a row").

### Phase 6: Quiz Endpoint
**Rationale:** Depends on mastery scores written by Phase 5. Kept separate to avoid premature coupling.
**Delivers:** `POST /quiz?scope=weak_spots&num_questions=7`, bottom-quartile mastery concept selection, Claude question generation, Claude answer grading, quiz results with concepts reviewed.

### Phase 7: Frontend — Graph View + Study Page
**Rationale:** Depends on stable graph and SRS APIs from Phases 5–6.
**Delivers:** React Flow graph with dagre layout using `@dagrejs/dagre` (NOT `dagre`), `@xyflow/react` (NOT `reactflow`), `nodeTypes` defined outside component body, `ConceptNode` wrapped in `React.memo`, 5s polling with layout recalculation skipped when node IDs unchanged, `fitView` called only on first render, node coloring by mastery, pulsing dot for struggle flags, slide-in node detail panel (not page navigation), SRS study page with front-reveal-then-grade flow, empty-queue completion state.
**Watch out for:** C-10 (dagre nodes at origin — copy official v12 example verbatim), C-11 (node re-render jank — nodeTypes outside component, React.memo on ConceptNode), m-4 (viewport jumping on poll).

### Phase 8: Dashboard + Library + Quiz Page
**Rationale:** Can be parallelized with Phase 7. Less risky than graph/study pages.
**Delivers:** Dashboard with cards-due-today count, weak concepts list, course management, Library page with source list and ingestion status per source, Quiz page with weak-spots launch, question/answer flow, results display, empty states for fresh install.

### Phase 9: Seed Data + Demo Script
**Rationale:** Requires full backend complete. The seed data quality determines whether the demo works.
**Delivers:** Seed script loading 3+ CS229 PDFs producing ~30–50 concepts, mastery scores with genuine variance (~25% weak / ~50% medium / ~25% strong), memorable weak-spot concept names, held-out PDF that adds new unreviewed concepts during the live demo drop.
**Watch out for:** M-5 (uniform mastery → random-looking weak-spots quiz — explicitly verify mastery distribution before demo day).

### Phase 10: Polish + Demo Hardening
**Rationale:** Final phase; depends on everything.
**Delivers:** Demo script tested end-to-end, README with macOS Accessibility permission setup step, live drop tested with exact browser and file type to be used in demo, fallback plan if live drop fails (web uploader on Library page), uvicorn running via `Ctrl-C` (not `kill -9`) during dev to avoid stuck processing rows.
**Watch out for:** C-2 (⌘V paste — add demo script note: click notch zone before pasting), demo-day risk register.

---

### Phase Ordering Rationale

The hard ordering constraint is: schema → ingest skeleton → pipeline → APIs → frontend. The NotchDrop fork can be built in parallel with the backend (it only depends on `POST /ingest` existing) but building it early while the backend is being stood up is lower risk than leaving Swift integration to the end. Seed data must come after the full pipeline is complete because it exercises every stage end-to-end and validates concept quality before the frontend is connected.

### Research Flags

**Phases needing explicit validation steps:**
- **Phase 4 (Concept Extraction):** Manual DB inspection of 10 concept nodes is not optional. Prompt quality determines demo card quality. Budget 1–2 prompt iteration cycles.
- **Phase 9 (Seed Data):** Verify mastery variance numerically: `SELECT mastery_score, count(*) FROM concepts GROUP BY round(mastery_score::numeric, 1) ORDER BY 1`. Confirm distribution before Phase 10.
- **Phase 1 (NotchDrop UTI):** Log all advertised UTI types on every drop event during development. Do not rely on manual testing alone — different browsers advertise different type sets.

**Phases with standard patterns (lower risk):**
- Phase 0 (Infra) — Docker Compose + Alembic are well-documented; main risk is the one Vector column gotcha
- Phase 5 (SRS endpoints) — SM-2 is a fixed published algorithm; main risk is the clamping bug
- Phase 8 (Dashboard/Library) — standard CRUD + polling; no novel patterns

---

## What to Watch Out for By Build Phase

| Phase | Highest-Risk Item | One-Line Mitigation |
|-------|------------------|---------------------|
| Phase 0: Infra | Alembic skipping Vector columns | Write migration manually; test on clean DB |
| Phase 1: Swift | UTI ordering: file-url shadows image | Check `public.image` before `public.file-url`; log all UTI types |
| Phase 1: Swift | `⌘V` paste fails when browser has focus | Notch must be key window first; note in demo script |
| Phase 1: Swift | Missing Accessibility permission — global monitor silent | `AXIsProcessTrustedWithOptions` check at startup |
| Phase 2: Backend | BackgroundTask lost on `--reload` | Startup reconciliation resets stuck rows to error |
| Phase 2: Backend | CORS blocks Swift URLSession | `allow_origins=["*"]` for local dev |
| Phase 2: Backend | Content-hash blocks re-ingestion after fixing bugs | Add `force=true` query parameter early |
| Phase 3: Embeddings | Wrong model used in one code path | Single `EMBEDDING_MODEL` constant; assert dimension before insert |
| Phase 3: Embeddings | ivfflat index on empty table | Use hnsw for concepts; defer ivfflat for chunks until after seed |
| Phase 4: Extraction | Claude returns invalid JSON | Use `tool_use` with strict schema; retry once on parse failure |
| Phase 4: Extraction | Hallucinated generic concepts ("Problem Solving") | Negative prompt instruction; manual inspection step is mandatory |
| Phase 4: Extraction | Prompt change has no effect (cache) | `TRUNCATE extraction_cache` after every prompt edit |
| Phase 5: SRS | `ease_factor` below 1.3 causes irrational intervals | Clamp after every update; unit test 10x "Again" case |
| Phase 5: SRS | Naive datetime in `due_at` | `datetime.now(timezone.utc)` everywhere |
| Phase 7: Frontend | All graph nodes at origin | Copy official xyflow.com v12 dagre example verbatim |
| Phase 7: Frontend | `nodeTypes` object recreated on every render | Define `nodeTypes` outside component body |
| Phase 7: Frontend | Viewport jumps every 5s during extraction | Skip dagre layout when node IDs are unchanged |
| Phase 9: Seed | All mastery scores at 0.5 → random weak-spots quiz | Explicit variance: 25% weak / 50% medium / 25% strong |
| Phase 10: Demo | Live drop fails with unknown file type | Test exact browser + file type 30 min before demo; have web uploader as fallback |

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack — package names and versions | HIGH | React Flow rename, dagre fork, pgvector index behavior all extensively documented; exact patch versions need live PyPI/npm verification before pinning |
| Stack — SM-2 algorithm | HIGH | Fixed published algorithm; implementation bugs are well-catalogued |
| Features — table stakes vs. differentiators | HIGH | Anki, Obsidian, Remnote, Readwise all well-documented through training cutoff; competitor patterns are stable |
| Architecture — FastAPI BackgroundTasks | HIGH | Official FastAPI docs consulted; behavior confirmed |
| Architecture — concept resolution thresholds | MEDIUM | 0.92/0.80 values informed by RAG system literature but not benchmarked against text-embedding-3-small specifically; treat as starting points |
| Pitfalls — Swift/NSItemProvider | HIGH | Well-documented Apple developer behavior; UTI ordering bugs are a recurring community issue |
| Pitfalls — Claude JSON extraction | MEDIUM | tool_use reliability based on training knowledge; verify against current Anthropic API docs before Phase 4 |
| Pitfalls — trafilatura SPA behavior | HIGH | Documented limitation; fallback strategy is standard |

**Overall confidence: HIGH** for build decisions; MEDIUM for threshold values that require empirical tuning (concept resolution, Claude prompt quality).

### Gaps to Address During Implementation

- **`claude-sonnet-4-5` model ID** — verify this exact string is live against the Anthropic API before Phase 4. The spec's model string is plausible but should be confirmed.
- **`@xyflow/react` exact v12 minor version** — run `npm info @xyflow/react` to confirm latest stable before pinning.
- **Concept resolution thresholds** — 0.92/0.80 are starting points. Plan for one manual inspection + threshold adjustment cycle after Phase 4 seed data is loaded.
- **Extraction prompt quality** — no amount of pre-research substitutes for one real extraction run against actual CS229 PDFs. Budget time to iterate on the prompt.
- **`ivfflat` lists value for chunks table** — use `lists=10` during development, rebuild with `lists=100` (or `sqrt(row_count)`) after seed data is loaded.

---

## Sources

### Primary (HIGH confidence)
- FastAPI BackgroundTasks official docs — task lifecycle, shutdown behavior
- pgvector README — hnsw vs ivfflat, lists heuristic, dimension enforcement
- React Flow / xyflow v12 migration guide — package rename, dagre separation, nodeTypes stability
- SM-2 algorithm (Wozniak 1987) — original specification; ease_factor floor, grade mapping
- PyMuPDF 1.24 changelog — import path changes
- SQLAlchemy 2.0 migration guide — AsyncSession patterns, raw SQL deprecation
- Apple Developer Documentation — NSItemProvider, NSEvent global monitors, Accessibility entitlements

### Secondary (MEDIUM confidence)
- RAG system literature (training data) — concept resolution threshold interpretation for text-embedding-3-small cosine space
- Anki, Obsidian, Remnote, Readwise feature documentation (training data) — table stakes validation, UX conventions
- pgvector community benchmarks — hnsw vs ivfflat query performance comparison
- Anthropic tool_use documentation — structured output reliability; verify against current API docs before Phase 4

### Tertiary (LOW confidence — verify before use)
- Exact patch versions for all packages — requires live `pip index versions` / `npm info` checks
- `claude-sonnet-4-5` model ID availability — verify against live Anthropic API
- trafilatura behavior on specific modern SPAs — version-dependent; test against actual student content sources

---
*Research completed: 2026-04-25*
*Ready for roadmap: yes*
