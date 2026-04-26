# Roadmap: Cortex

**Project:** Cortex — student knowledge-graph + notch-drop ingestion
**Milestone:** v1 (hackathon demo)
**Granularity:** standard
**Created:** 2026-04-25

---

## Phases

- [x] **Phase 1: Infrastructure** — Postgres + pgvector running, schema migrated, health endpoint live, seed data loaded, 5/5 tests green
- [ ] **Phase 2: Ingest + Parsing + Notch** — Files dropped into notch arrive at backend as parsed chunks with embeddings
- [ ] **Phase 3: Extraction, Resolution & Edges** — Concepts extracted, deduplicated per course, edges inferred, depth computed
- [ ] **Phase 4: Flashcards, Struggle & Quiz** — Flashcard nodes generated, struggle signals detected, quiz endpoint live
- [ ] **Phase 5: Graph API** — All API contracts stable and returning correct graph payloads
- [ ] **Phase 6: Frontend** — Graph, flashcard, quiz, library, and dashboard views functional
- [ ] **Phase 7: Demo Readiness** — Seed data loaded with variance, README complete, all acceptance tests pass

---

## Phase Details

### Phase 1: Infrastructure
**Goal**: The development foundation is solid — a fresh `docker compose up` produces a healthy Postgres+pgvector database with all tables, indexes, and extensions in place, and the API server starts clean with a passing health check.
**Depends on**: Nothing
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05
**Success Criteria** (what must be TRUE):
  1. `docker compose up -d` completes without error and `docker compose ps` shows the DB container healthy
  2. `alembic upgrade head` on a fresh (empty) DB creates all tables, the `vector` extension, hnsw index on `concepts.embedding`, and all foreign keys — verified by `\d` in psql
  3. `GET /health` returns HTTP 200 `{"status": "ok"}`
  4. `scripts/seed_demo.py` runs against the migrated DB and produces at least one course row and user_id=1 row
  5. `.env.example` is present and documents every environment variable referenced in the codebase
**Plans**: 5 plans

Wave 0
- [x] 01-01-PLAN.md — Test stubs (pytest config, RED state tests)

**Wave 1** *(blocked on Wave 0 completion)*
- [x] 01-02-PLAN.md — Docker Compose, .env.example, requirements, config/database/models

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 01-03-PLAN.md — Alembic migration (hand-written) + run on fresh DB

**Wave 3** *(blocked on Wave 2 completion)*
- [x] 01-04-PLAN.md — FastAPI app (lifespan, CORS, health endpoint)

**Wave 4** *(blocked on Wave 3 completion)*
- [x] 01-05-PLAN.md — Seed script + full phase verification

Cross-cutting constraints:
- `pgvector/pgvector:pg16` Docker image enforced in 01-02
- `expire_on_commit=False` on all session factories enforced in 01-02, 01-05
- Hand-written Alembic migration only (no autogenerate) enforced in 01-03

**Stack notes**:
  - Docker image: `pgvector/pgvector:pg16` (NOT `postgres:16`)
  - Alembic migration must be hand-written — autogenerate does NOT detect `pgvector.sqlalchemy.Vector` columns
  - Include `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` before table creation in migration
  - hnsw index for `concepts.embedding` (empty-table safe); defer ivfflat for `chunks.embedding` until after seed load
  - Test migration on clean DB: `docker compose down -v && docker compose up -d && alembic upgrade head`

### Phase 2: Ingest + Parsing + Notch
**Goal**: A student can drag a PDF or URL into the macOS notch and see a status pill confirm delivery; the backend creates a source row, parses content into chunks, embeds them, and queues them for extraction — all without blocking the HTTP response.
**Depends on**: Phase 1
**Requirements**: ING-01, ING-02, ING-03, ING-04, ING-05, ING-06, ING-07, ING-08, ING-09, ING-10, ING-11, ING-12, ING-13, ING-14, ING-15, PARSE-01, PARSE-02, PARSE-03, PARSE-04, PARSE-05, PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06, PIPE-07
**Success Criteria** (what must be TRUE):
  1. Dragging a PDF into the notch shows "Sending to Cortex…" then "Sent to [Course Name]"; the DB has a new `sources` row with `source_type=pdf` and `status=processing` or `status=done`
  2. `POST /ingest` returns `{source_id, status: "pending"}` within 200ms regardless of file size; the pipeline continues in the background
  3. Dropping the same PDF a second time is a no-op — `content_hash` deduplication fires, the source row has `metadata.duplicate_of` set, and no new chunks are created
  4. Dropping a URL routes correctly: arXiv `abs/` links auto-rewrite to PDF; all other URLs produce clean text chunks via trafilatura with title from `<title>` tag
  5. When no courses exist, the notch shows a "Name this course" input before upload; when courses exist and confidence ≥ 0.65, the course is auto-assigned silently
  6. Server restart while sources are `processing` resets them to `pending` on next startup (startup reconciliation hook)
**Plans**: 8 plans

**Wave 1** *(foundation — schema)*
- [x] 02-01-PLAN.md — Alembic migration 0002_course_embeddings (adds courses.embedding Vector(1536))

**Wave 2** *(parallel — no inter-dependencies)*
- [x] 02-02-PLAN.md — Parsers module (PDF/URL/image/text parsers)
- [x] 02-03-PLAN.md — Course API endpoints (GET/POST /courses, GET /courses/match)
- [x] 02-04-PLAN.md — NotchDrop clone + NOTICE.md + Cortex/ directory

**Wave 3** *(depends on 02-01, 02-02, 02-03)*
- [x] 02-05-PLAN.md — Background pipeline + POST /ingest + dedup + courses.embedding backfill

**Wave 4** *(depends on 02-04, 02-03)*
- [x] 02-06-PLAN.md — Swift Cortex module: CortexClient, CortexIngest, CortexSettings, CortexStatusView [notch-specialist]

**Wave 5** *(depends on 02-06)*
- [x] 02-07-PLAN.md — CortexCourseTab + surgical edit + ⌘V handler [notch-specialist]

**Wave 6** *(depends on 02-05, 02-07)*
- [ ] 02-08-PLAN.md — Integration tests + phase gate verification

**Stack notes**:
  - CORS: `allow_origins=["*"]` for local dev — Swift `URLSession` sends no `Origin` header; missing-Origin requests must not be blocked
  - NSItemProvider UTI priority: check `public.png` / `public.jpeg` BEFORE `public.file-url` to avoid temp-file URLs from browser image drags
  - FastAPI `BackgroundTasks` pattern: open a fresh `async with AsyncSession(engine) as session:` inside EACH pipeline stage — do not pass a single session through all 8 stages
  - Add `force=true` query param to `/ingest` to bypass `content_hash` dedup during development
  - `#if CORTEX_ENABLED` compile-time guard in NotchDrop surgical edit to preserve fallback behavior
  - Session default: last-selected course ID stored in `UserDefaults` for same-session pre-selection
**UI hint**: yes

### Phase 3: Extraction, Resolution & Edges
**Goal**: After a source is fully parsed and chunked, the pipeline extracts meaningful concept nodes, merges duplicates within the same course, infers prerequisite and co-occurrence edges, and writes a BFS depth value to each concept — producing a queryable knowledge graph.
**Depends on**: Phase 2
**Requirements**: EXTRACT-01, EXTRACT-02, EXTRACT-03, EXTRACT-04, EXTRACT-05, RESOLVE-01, RESOLVE-02, RESOLVE-03, RESOLVE-04, RESOLVE-05, EDGE-01, EDGE-02, EDGE-03, EDGE-04
**Success Criteria** (what must be TRUE):
  1. Processing a CS229 PDF produces 10–40 concept nodes with populated `title`, `definition`, `key_points`, `gotchas`, `examples`; no concept has a generic title like "Problem Solving" or an abbreviation-only title like "NN"
  2. Dropping the same PDF twice into the same course produces the same concept nodes, not duplicates (content_hash dedup + resolution working together)
  3. Two different PDFs covering "Gradient Descent" in the same CS229 course produce exactly ONE concept node (RESOLVE-05 verified in psql)
  4. After edge inference, `concepts.depth` is a non-null integer for every concept in the course; root concept nodes (no incoming prerequisite edges) get `depth=1`; the course node itself is virtual depth=0 synthesized by the Phase 5 graph API from the `courses` table, not stored in `concepts.depth`
  5. The `extraction_cache` table has rows after processing; rerunning the pipeline on the same source skips LLM calls (cache hits logged)
**Plans**: 4 plans

**Wave 0** *(TDD RED — test scaffolding + module skeletons)*
- [ ] 03-01-PLAN.md — Test stubs (RED state) + extractor/resolver/edges module skeletons

**Wave 1** *(parallel — depends on Wave 0)*
- [ ] 03-02-PLAN.md — LLM Extraction stage (extractor.py, EXTRACT-01..05)
- [ ] 03-03-PLAN.md — Concept Resolution stage (resolver.py, RESOLVE-01..05)

**Wave 2** *(depends on Wave 1)*
- [ ] 03-04-PLAN.md — Edge Inference + BFS depth + pipeline.py wiring (edges.py, EDGE-01..04)

**Stack notes**:
  - Use Claude `tool_use` with strict JSON Schema (`additionalProperties: false`) — never parse free-text JSON
  - Retry once on parse failure; log malformed responses
  - Negative extraction prompt: "Do not extract generic study skills, acronym-only concepts, or procedural steps"
  - Resolver cosine query MUST include `AND course_id = :course_id` — no cross-course merges ever
  - After this phase: manually inspect 10 concept nodes in psql before proceeding; tune thresholds if over/under-merging
  - `TRUNCATE extraction_cache` after every extraction prompt edit during development
  - Max 5 chunks in parallel (EXTRACT-05); prerequisite edge inference batched max 50 concepts/call

### Phase 4: Flashcards, Struggle & Quiz
**Goal**: Every new concept node automatically gets 3–6 flashcard nodes connected to it; struggle signals are detected and stored on concepts; a quiz can be generated on demand scoped to a course or its struggle signals — all without any mastery scoring.
**Depends on**: Phase 3
**Requirements**: FLASH-01, FLASH-02, FLASH-03, FLASH-04, FLASH-05, FLASH-06, STRUGGLE-01, STRUGGLE-02, STRUGGLE-03, STRUGGLE-04, STRUGGLE-05, STRUGGLE-06, QUIZ-01, QUIZ-02, QUIZ-03, QUIZ-04, QUIZ-05, QUIZ-06
**Success Criteria** (what must be TRUE):
  1. After processing a PDF, every concept node has 3–6 attached flashcard nodes in the DB; card types include at least `definition` and `application`; no card has due dates or ease factors
  2. Submitting a `POST /quiz` with `{course_id, num_questions: 7}` returns a quiz with 7 questions mixing MCQ, short_answer, and application types
  3. A concept node that has ≥ 3 similar student questions (from a chat_log source) has `struggle_signals` containing `repeated_confusion`
  4. `GET /quiz/{id}/results` returns a score breakdown and a list of concept titles to review
  5. Flipping a flashcard (front → back) requires no grading action — it is purely a display toggle with no DB write
**Plans**: 4 plans

**Wave 0** *(TDD RED — test scaffolding + module skeletons)*
- [ ] 04-01-PLAN.md — Test stubs (RED state) + flashcards.py/signals.py/quiz.py/schemas/quiz.py skeletons

**Wave 1** *(parallel — depends on Wave 0)*
- [ ] 04-02-PLAN.md — Flashcard generation stage: flashcards.py + pipeline.py stage 7 wiring (FLASH-01..06)
- [ ] 04-03-PLAN.md — Struggle signal detection stage: signals.py + pipeline.py stage 8 wiring (STRUGGLE-01..06)

**Wave 2** *(depends on Wave 1)*
- [ ] 04-04-PLAN.md — Quiz API: quiz.py full implementation + router.py registration (QUIZ-01..06)

**Stack notes**:
  - No SRS: flashcard nodes have no `due_at`, `ease_factor`, or `repetitions` columns — this is v2 scope
  - No mastery scoring: `struggle_signals` feed quiz generation only, not a 0–1 score
  - Quiz node is attached to course root (QUIZ-01), not to individual concept nodes
  - Flashcard generation: max 3 parallel LLM calls via asyncio.Semaphore(3)
  - `flag_modified(obj, "field")` required for ANY in-place mutation of `quizzes.questions` or `concepts.struggle_signals`
  - `result.scalars().unique().all()` required when joining Concept via ConceptSource to prevent duplicates
  - D-11: signals dict only includes evaluated keys — never set unevaluated keys to False
  - `POST /quiz/{id}/answer` grades free-response via Claude tool_use; returns next question or final results inline

### Phase 5: Graph API
**Goal**: All backend API contracts are stable and return correctly shaped graph payloads — course nodes, concept nodes, flashcard nodes, quiz nodes, all edges, and course-matching — so the frontend can be built against them without rework.
**Depends on**: Phase 4
**Requirements**: GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-04, GRAPH-05, GRAPH-06, GRAPH-07
**Success Criteria** (what must be TRUE):
  1. `GET /courses/{id}/graph` returns a JSON payload with nodes of types `course`, `concept`, `flashcard`, `quiz` and edges typed `contains`, `co_occurrence`, `prerequisite`, `related` — verifiable with `curl | jq`
  2. `GET /concepts/{id}` returns all detail fields: `summary`, `key_points`, `gotchas`, `examples`, `student_questions`, `source_citations`, `flashcard_count`, `struggle_signals`
  3. `GET /courses/match?hint=backpropagation` returns `{course_id, title, confidence}` for the best-matching course; returns `null` when no course confidence exceeds 0.65
  4. `POST /courses` creates a course and returns it with an `id`; `GET /courses` returns all courses for user_id=1
  5. The graph endpoint includes flashcard nodes connected to their parent concept and quiz nodes connected to the course root
**Plans**: 4 plans

**Wave 0** *(TDD RED — test scaffolding + schema skeletons)*
- [ ] 05-01-PLAN.md — Test stubs (RED state) + graph/concept schemas + concepts.py skeleton

**Wave 1** *(parallel — no shared files)*
- [ ] 05-02-PLAN.md — GET /courses/{id}/graph + _build_graph_payload + /match consistency fix (GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-05, GRAPH-06, GRAPH-07)
- [ ] 05-03-PLAN.md — GET /concepts/{id} full implementation + router.py registration (GRAPH-04)

**Wave 2** *(depends on Wave 1)*
- [ ] 05-04-PLAN.md — Full test suite + curl smoke tests + human sign-off

Cross-cutting constraints:
- Route registration order: `/match` BEFORE `/{course_id}/graph` in courses.py — FastAPI matches in order
- No embedding vectors in graph response — `_build_graph_payload` builds data dicts explicitly
- All node IDs are prefixed strings: `"course-{id}"`, `"concept-{id}"`, `"flashcard-{id}"`, `"quiz-{id}"`
- `definition` → `summary` rename applied at explicit constructor (not via from_attributes auto-mapping)
- "contains" edges synthesized in Python from FK — the edges table has NO contains rows (EDGE-01)
- N+1 prevention: flashcards and edges loaded with single IN queries across all concept_ids

### Phase 6: Frontend
**Goal**: A student can open the web app, see their course graph with concept nodes colored by struggle signal, click a concept to read its details and launch flashcard review, generate and take a quiz, and see their library of ingested sources — all with correct empty states.
**Depends on**: Phase 5
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08, UI-09, UI-10, UI-11
**Success Criteria** (what must be TRUE):
  1. The course graph renders with dagre layout (no nodes piled at origin); concept nodes are sized by `source_count`; nodes with struggle signals show a pulsing red indicator; edge types are visually distinct (thick/solid/dashed/dotted)
  2. Clicking a concept node opens a slide-in detail panel showing summary, gotchas (amber highlight), key_points, source citations, flashcard count, and a "View Flashcards" button
  3. "View Flashcards" opens flip-card mode: front is shown, "Show Answer" reveals back, "Next" advances — no grade buttons, no scheduling
  4. Clicking the quiz node on the graph opens the quiz walkthrough; the final screen shows score and "Concepts to review" list
  5. The library page shows all sources with correct status badges; the web uploader is present and labeled as a fallback
  6. When no sources are processing, polling stops; while any source is `pending` or `processing`, the graph re-fetches every 5s
**Plans**: TBD
**Stack notes**:
  - Package: `@xyflow/react` (NOT `reactflow`) — v12 canonical import
  - Dagre: `@dagrejs/dagre` (NOT `dagre`) — use `import * as dagre from '@dagrejs/dagre'`
  - Define `nodeTypes` outside the component body (prevent object recreation on every render)
  - Wrap `ConceptNode` in `React.memo`
  - Call `setTimeout(() => reactFlowInstance.fitView(), 0)` after `setNodes(layoutedNodes)` on first render only
  - Skip dagre layout recalculation when node IDs are unchanged (prevents viewport jumps every 5s)
  - Next.js 14.2.x — do NOT upgrade to 15
**UI hint**: yes

### Phase 7: Demo Readiness
**Goal**: A fresh clone can be set up in under 10 minutes, the seed script produces a convincing demo state with real mastery variance, the live-drop path works end-to-end, and all 11 acceptance test steps pass.
**Depends on**: Phase 6
**Requirements**: DEMO-01, DEMO-02, DEMO-03, DEMO-04, DEMO-05
**Success Criteria** (what must be TRUE):
  1. `scripts/seed_demo.py` runs on a fresh DB and produces ~20 concept nodes with ≥ 3 having active struggle signals and ≥ 3 without; struggle signals are visually distinguishable in the graph
  2. The seed holds out exactly 1 PDF and 1 URL; dropping the held-out PDF during the demo adds new concept nodes visible within ~60s
  3. `POST /quiz` with `scope=struggle_signals` returns a targeted 7–10 question quiz referencing recognizable CS229 concept names (not generic concepts)
  4. README contains: prerequisite install steps, macOS Accessibility permission setup for ⌘V, `docker compose up`, alembic migration, seed script, and a demo script with exact steps
  5. All 11 acceptance test steps from spec §8 pass on a clean DB without manual intervention
**Plans**: TBD

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Infrastructure | 5/5 | Complete | 2026-04-25 |
| 2. Ingest + Parsing + Notch | 0/8 | Not started | - |
| 3. Extraction, Resolution & Edges | 0/4 | Planned | - |
| 4. Flashcards, Struggle & Quiz | 0/4 | Planned | - |
| 5. Graph API | 0/4 | Planned | - |
| 6. Frontend | 0/0 | Not started | - |
| 7. Demo Readiness | 0/0 | Not started | - |

---

## Requirement Coverage

**Total v1 requirements:** 71
**Mapped:** 71
**Unmapped:** 0 ✓

| Category | Count | Phase |
|----------|-------|-------|
| INFRA-01–05 | 5 | Phase 1 |
| ING-01–15 | 15 | Phase 2 |
| PARSE-01–05 | 5 | Phase 2 |
| PIPE-01–07 | 7 | Phase 2 |
| EXTRACT-01–05 | 5 | Phase 3 |
| RESOLVE-01–05 | 5 | Phase 3 |
| EDGE-01–04 | 4 | Phase 3 |
| FLASH-01–06 | 6 | Phase 4 |
| STRUGGLE-01–06 | 6 | Phase 4 |
| QUIZ-01–06 | 6 | Phase 4 |
| GRAPH-01–07 | 7 | Phase 5 |
| UI-01–11 | 11 | Phase 6 |
| DEMO-01–05 | 5 | Phase 7 |

---

*Roadmap created: 2026-04-25*
*Last updated: 2026-04-25 — Phase 4 planning complete (4 plans across 3 waves; all FLASH/STRUGGLE/QUIZ requirements mapped)*
