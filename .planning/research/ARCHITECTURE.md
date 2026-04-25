# Architecture Patterns

**Domain:** Knowledge-graph + RAG + spaced-repetition student app
**Researched:** 2026-04-25
**Confidence:** MEDIUM-HIGH (FastAPI/BackgroundTasks from official docs; pgvector/React Flow/resolution from training knowledge at Aug-2025 cutoff; Swift isolation from established patterns)

---

## Recommended Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Cortex Drop (macOS Swift/SwiftUI)                               │
│  NotchDrop fork  ──►  Cortex/ subfolder                          │
│    CortexIngest.swift  CortexSettings.swift                      │
│    CortexDropHandler.swift  CortexStatusPill.swift               │
│  POST multipart/JSON ──────────────────────────────────────────► │
└──────────────────────────────────────────────────────────────────┘
                          │  HTTP (URLSession, no auth)
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  Cortex API  (FastAPI + uvicorn, single process)                 │
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────┐  │
│  │  Routers   │  │ Background │  │  Services  │  │  Models  │  │
│  │ /ingest    │  │  Pipeline  │  │ parser     │  │ SQLAlch. │  │
│  │ /courses   │  │ (starlette │  │ embedder   │  │  ORM     │  │
│  │ /graph     │  │ BackgrdTsk)│  │ extractor  │  │          │  │
│  │ /flashcard │  │            │  │ resolver   │  │          │  │
│  │ /quiz      │  │ stage FSM  │  │ graph_svc  │  │          │  │
│  └────────────┘  └─────┬──────┘  │ srs_svc    │  └──────────┘  │
│                        │         └────────────┘                 │
└────────────────────────┼─────────────────────────────────────── ┘
                         │
           ┌─────────────▼─────────────┐
           │  Postgres 16 + pgvector   │
           │  (Docker Compose)         │
           │  tables: sources, chunks, │
           │  concepts, edges,         │
           │  flashcards, quiz_*,      │
           │  extraction_cache         │
           │  indexes: ivfflat on      │
           │  chunk_embedding,         │
           │  concept_embedding        │
           └───────────────────────────┘
                         │  (reads graph + flashcards)
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  Cortex Web  (Next.js 14 App Router)                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │Dashboard │  │  Graph   │  │  Study   │  │  Library / Quiz  │ │
│  │          │  │ReactFlow │  │  page    │  │  pages           │ │
│  │          │  │+ dagre   │  │  SRS     │  │                  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘ │
│  poll /graph every 5s while source.status == processing         │
└──────────────────────────────────────────────────────────────────┘
```

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| CortexDrop (Swift) | Intercept drops/pastes, show status pill, fire POST /ingest | Cortex API only (URLSession) |
| CortexSettings (Swift) | Persist backend URL + active course ID (UserDefaults) | CortexDrop |
| FastAPI routers | Request/response contracts; return source_id + "pending" immediately | Background pipeline, Postgres via SQLAlchemy |
| Background pipeline | 8-stage ingest FSM; writes status to sources table at each stage | Postgres; calls Claude API; calls OpenAI embeddings API |
| Parser service | PDF→text (pymupdf), URL→text (httpx+trafilatura), image→markdown (Claude vision), text→normalized | Background pipeline |
| Embedder service | Batch embed chunks and concept names; text-embedding-3-small 1536-dim | OpenAI API; background pipeline |
| Extractor service | Per-chunk concept extraction via Claude; reads/writes extraction_cache | Claude API; Postgres |
| Resolver service | Course-scoped cosine ANN query → merge/tiebreak/new | Postgres pgvector; Claude API (tiebreaker) |
| Graph service | BFS depth calculation; edge creation; GET /graph serialization | Postgres |
| SRS service | SM-2 scheduling; mastery update; due-card queries | Postgres |
| Quiz service | Question generation, scope filtering, Claude grading | Postgres; Claude API |
| Cortex Web | Visualize graph, drive study sessions, display quiz | Cortex API (fetch/poll) |

---

## Data Flow

### Ingest Pipeline (8 stages, sequential within one BackgroundTask)

```
POST /ingest
  → write sources row (status=pending), return {source_id}
  → BackgroundTasks.add_task(run_pipeline, source_id)

run_pipeline(source_id):
  [1] PARSE       → sources.raw_text, sources.title
  [2] CHUNK       → insert chunks rows (text, page_num, hash)
  [3] EMBED       → update chunks.embedding (batch, 5 parallel)
  [4] EXTRACT     → per chunk: check extraction_cache → Claude → concepts[]
  [5] RESOLVE     → per concept: ANN query on concepts.embedding
                     ≥0.92 → merge (update chunk_concepts fk)
                     0.80–0.92 → Claude tiebreaker → merge or new
                     <0.80 → insert new concept, embed name
  [6] EDGES       → co-occurrence edges (chunk co-mention)
                    prerequisite edges (LLM inference)
                    course→concept (contains) edges
  [7] FLASHCARDS  → per new concept: Claude generates 3–6 cards
                    (3 parallel generations)
  [8] MASTERY     → BFS depth on course graph
                    initialize mastery_score=0.5 for new concepts
                    update sources.status = done
  → on any exception: sources.status=error, log stack trace, return
```

### Graph Query Flow

```
GET /courses/{id}/graph
  → SELECT concepts WHERE course_id=id
  → SELECT edges WHERE course_id=id
  → serialize: {nodes: [{id, label, depth, mastery, struggle_flags}],
                edges: [{source, target, type}]}

Cortex Web:
  → useEffect poll every 5s while any source.status == "processing"
  → dagre layout: rankdir=TB, ranksep by depth, node size by source_count
  → node color: mastery<0.4→red, <0.7→yellow, ≥0.7→green
  → pulsing dot: struggle_flags nonempty
```

### Study/SRS Flow

```
GET /flashcards/due
  → SELECT WHERE due_at <= now() ORDER BY due_at LIMIT 20
POST /flashcards/{id}/review  {grade: 1|3|4|5}
  → SM-2 update: interval, ease_factor, repetitions, due_at
  → mastery_score += delta (grade-mapped)
  → return {next_due, new_interval, next_card_id}
```

---

## Focus Area Findings

### 1. FastAPI BackgroundTasks — Sufficiency and Failure Mode

**Verdict: Sufficient for hackathon scope with one mitigation required.**

Official FastAPI docs confirm: BackgroundTasks runs in the same process as uvicorn. If the server process dies mid-pipeline (crash, OOM, SIGKILL, Ctrl-C during dev), the in-flight task is lost with no automatic recovery. The sources row remains at whatever status it had last been written to (e.g., `status=chunking`), and the pipeline never resumes.

**Why this is acceptable for Cortex:**
- Single-user, local demo. The user knows if they restarted the server.
- The mitigation is already in the spec: `sources.status` is written at every stage transition. On restart, a manual recovery path (or a startup hook that re-queues `status NOT IN ('done','error')` rows) is trivially addable.
- No Redis, no Celery, no arq worker process to manage. The hackathon timeline (the spec's Phase 1 is 5-6 hours) does not justify the setup cost of a proper task queue.

**The one required mitigation — startup re-queue hook:**
```python
@app.on_event("startup")
async def requeue_stuck_pipelines():
    # Find rows stuck in intermediate states from a prior crash
    async with get_session() as session:
        stuck = await session.execute(
            select(Source).where(
                Source.status.not_in(["done", "error", "pending"])
            )
        )
        for source in stuck.scalars():
            background_tasks = BackgroundTasks()  # ← won't work at startup
            # Better: just reset to pending and let the next ingest trigger it,
            # or expose POST /sources/{id}/retry endpoint
            source.status = "error"
            source.error_msg = "server restarted mid-pipeline; use retry"
            await session.commit()
```

**Practical recommendation:** At startup, mark any non-terminal stuck rows as `status=error` with message "server restart". Add a `POST /sources/{id}/retry` endpoint that re-enqueues the pipeline. This gives the demo a clean recovery story without Celery.

**arq/Celery: Not warranted.** arq requires Redis. Celery requires a broker (Redis or RabbitMQ) and a separate worker process. Both add ~30-60 min of setup that buys nothing for a single-user local demo where restarts are observable.

**Confidence:** HIGH (from official FastAPI docs, direct quotes; reinforced by Starlette source behavior).

---

### 2. pgvector ivfflat Configuration

**Verdict: The spec's lists=100 (chunks) and lists=50 (concepts) are defensible but slightly over-indexed for the expected dataset. HNSW is worth considering.**

**The standard ivfflat lists heuristic** (from pgvector README and community practice):
- `lists` ≈ `sqrt(n_rows)` for datasets up to ~1M rows
- For 10K rows: `sqrt(10000)` = 100 → spec's `lists=100` is exactly the textbook value for the upper bound
- For 1K rows (more realistic early): `sqrt(1000)` ≈ 32 → `lists=100` will underperform because most lists will be empty, causing spurious probes

**Practical implication:** ivfflat requires data in the table before the index is built (it clusters existing vectors). An index built on an empty table or a handful of rows is essentially useless until rebuilt with `REINDEX`. The spec should build the index after seed data is loaded, not in the initial Alembic migration.

**HNSW comparison:**
- HNSW does not require pre-built centroids, so it stays accurate as rows are inserted incrementally
- HNSW has higher memory usage (~3x vs ivfflat for the same dataset)
- HNSW query performance is generally better (no `probes` tuning needed)
- For a hackathon dataset (<100K vectors), the memory difference is negligible
- **Recommendation: prefer HNSW for the concepts table** (small, grows incrementally, queried for resolution on every ingest) and keep ivfflat for the chunks table (larger, queried for RAG retrieval only)

**Recommended index definitions:**
```sql
-- chunks: ivfflat is fine, but build AFTER seed data
-- lists=100 is correct for ~10K chunks; use lists=10 in dev until seeded
CREATE INDEX CONCURRENTLY chunks_embedding_idx
  ON chunks USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- concepts: HNSW preferred (incremental inserts, small table, latency-critical)
CREATE INDEX CONCURRENTLY concepts_embedding_idx
  ON concepts USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);
```

**For the resolver ANN query**, set `SET ivfflat.probes = 10` (or hnsw ef_search equivalent) at session level in the resolver service. Default probes=1 will miss many neighbors.

**Confidence:** MEDIUM-HIGH (pgvector README guidelines + established community sqrt(n) rule; specific values extrapolated from training knowledge, not verified against pgvector v0.7+ release notes).

---

### 3. Concept Resolution Architecture

**Verdict: The 0.92/0.80 thresholds are reasonable starting points. The architecture is sound but has three known failure modes.**

**Threshold context from RAG/NLP literature:**
- 0.92 is a high-confidence merge threshold for `text-embedding-3-small` (1536-dim). At this score, two concept names are almost certainly the same concept or alternate phrasings. This is a conservative, safe choice.
- 0.80–0.92 is the genuine ambiguity zone. "Support Vector Machine" and "Support Vector Classifier" might score ~0.87. The LLM tiebreaker is the right call here.
- <0.80 as "new concept" is reasonable: genuinely distinct concepts in a course rarely score above 0.75–0.78 with `text-embedding-3-small` for the same model embedding space.

**Specific to `text-embedding-3-small`:** The model uses cosine similarity in a normalized space. The 0.92 / 0.80 boundary maps to ~23° / ~37° angular separation, which aligns with practitioner experience for concept-level entity resolution. The spec's note "these are starting points — inspect after Phase 4" is the correct discipline.

**Known failure modes:**

**Failure mode A — Abbreviation drift.** "NN", "Neural Net", and "Neural Network" may score below 0.92 with each other because the embedding for an acronym differs from its expansion. Short concept names (≤3 chars) are high-risk. Mitigation: in the extractor prompt, instruct the model to always return the full canonical form, never abbreviations.

**Failure mode B — Cross-course pollution (already handled).** The spec's course-scoping is the correct fix. Without it, "Gradient Descent" in ML and "Gradient Descent" in an optimization course would incorrectly merge into one node. The course_id filter in the ANN query prevents this.

**Failure mode C — Threshold drift across documents.** The first few documents in a course define the "canonical" concept embeddings. Later documents with slightly different phrasing (e.g., a textbook vs. a lecture slide) can produce two near-duplicate nodes if the resolver was run before the course had enough vocabulary to cluster correctly. Mitigation: the spec's `content_hash` dedup helps at the source level; at the concept level, the "inspect after Phase 4" tuning step is the right safeguard.

**LLM tiebreaker cost:** Every ambiguous pair (0.80–0.92) triggers a Claude API call. At hackathon scale this is acceptable, but the `extraction_cache` should not absorb tiebreaker calls (they're pair-specific and won't repeat meaningfully). The cache is correctly scoped to `(chunk_hash, model_version)` per the spec.

**Confidence:** MEDIUM (threshold values informed by published RAG system post-mortems and SBERT documentation patterns; not verified against a live benchmark for `text-embedding-3-small` specifically).

---

### 4. React Flow + Dagre Layout

**Verdict: Dagre is NOT bundled with React Flow. It must be installed separately. `@xyflow/react` v12 (the current major) removed the layout dependency entirely. Use `dagre` or `@dagrejs/dagre` package.**

**React Flow naming:** As of v11+, the npm package is `@xyflow/react` (previously `reactflow`). The library moved to the xyflow monorepo. "React Flow v12" in the spec refers to `@xyflow/react` v12.x.

**Dagre installation:** Dagre is not and has never been bundled with React Flow. The canonical example from the React Flow docs uses:
```
npm install @xyflow/react dagre
```
or
```
npm install @xyflow/react @dagrejs/dagre
```

`@dagrejs/dagre` is the actively maintained fork (dagrejs org) of the original `dagre` package, which was abandoned around 2018. The original `dagre` package still works but receives no updates. For a new project, prefer `@dagrejs/dagre`.

**Standard pattern for rooted DAG with depth-based ranking:**
```typescript
import dagre from '@dagrejs/dagre';
import { useLayoutEffect } from 'react';
import { useReactFlow, useNodesState, useEdgesState } from '@xyflow/react';

const dagreGraph = new dagre.graphlib.Graph();
dagreGraph.setDefaultEdgeLabel(() => ({}));

function getLayoutedElements(nodes, edges, direction = 'TB') {
  dagreGraph.setGraph({ rankdir: direction, ranksep: 80, nodesep: 40 });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 172, height: 36 });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagre.layout(dagreGraph);

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - 172 / 2,
        y: nodeWithPosition.y - 36 / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}
```

**Depth-based rank pinning:** To force the course root node to rank 0 and concept nodes to their BFS depth rank, set dagre node rank manually via `dagreGraph.setNode(id, { rank: depth })`. This requires dagre's `rank` option, which is supported in `@dagrejs/dagre` but not well-documented. Alternative: pre-sort nodes by depth and rely on edge direction alone, which dagre's TB layout naturally respects for a DAG.

**React Flow v12 breaking change note:** v12 switched to a pure ESM package and requires React 18+. The `useReactFlow` hook and `fitView` API changed signatures. The dagre integration pattern itself is unchanged but ensure `@xyflow/react` ≥12.0.0 and React ≥18.0.0 in `package.json`.

**Confidence:** MEDIUM-HIGH (React Flow/xyflow naming and dagre separation confirmed from React Flow docs fetched above and training knowledge; `@dagrejs/dagre` fork status from training knowledge at Aug-2025 cutoff; v12 ESM change from release notes in training data).

---

### 5. NotchDrop Fork — Swift Module Isolation

**Verdict: The `Cortex/` subfolder approach is the correct isolation strategy for this type of fork. It is the standard pattern for surgical additions to an existing Swift app target.**

**How Swift app targets work:** A Swift app target compiles all `.swift` files in its source directories. Files in a subfolder are automatically included in the same module (the app module). There is no separate Swift module boundary at the folder level unless you create a Swift Package (separate target).

**The `Cortex/` subfolder approach means:**
- All four Cortex Swift files (`CortexIngest.swift`, `CortexDropHandler.swift`, `CortexSettings.swift`, `CortexStatusPill.swift`) are in the `NotchDrop` app module
- They can freely access `internal` symbols from the rest of NotchDrop without any import
- The diff against upstream is minimal: add the folder, add the four files, make one surgical edit to the tray drop handler

**Alternative considered — separate Swift Package (Swift Package Manager target):**
- Would give genuine module isolation (`import CortexModule` at call site)
- Would require the original `NotchDrop` target to declare a dependency on the package
- Changes `Package.swift` or the `.xcodeproj`, creating a larger diff and more merge friction on upstream updates
- Not warranted for a 4-file addition in hackathon scope

**Why subfolder is the right call:**
1. NotchDrop is an `.xcodeproj`-based project (not a SPM package), so adding a new SPM target would require project file surgery
2. The 4 Cortex files are small, cohesive, and don't need symbol isolation — they only call _into_ NotchDrop, not the other way around
3. Upstream merge cost: with the subfolder approach, `git diff upstream/main HEAD` shows exactly one modified file (the tray drop handler) plus four new files in `Cortex/`. Clean, reviewable.

**The surgical edit pattern:** The spec calls for editing one existing file in NotchDrop (the tray drop handler) to add a Cortex dispatch call. The right implementation is:
```swift
// In existing NotchDrop drop handler:
#if CORTEX_ENABLED
    CortexDropHandler.shared.handle(providers: providers, courseId: CortexSettings.shared.activeCourseId)
#else
    // original NotchDrop file-shelf behavior
#endif
```
This keeps the original behavior intact and makes the Cortex addition trivially removable. The `CORTEX_ENABLED` flag is set in the Cortex build scheme's Swift flags, not hardcoded.

**Pasteboard handling:** `NSItemProvider` priority order (image → URL → string) is correct for macOS drag sources. Images from browsers arrive as both `public.image` and `public.url`; checking image first prevents accidentally ingesting the CDN URL when the user intended to drop the image.

**Confidence:** HIGH (established Swift project patterns; no external verification source needed for folder-based module scope, which is fundamental to Swift's compilation model).

---

## Suggested Build Order and Implications

The spec's build order (Phase 0 → 2 → 1 → 3 → 4 → 5 → 7 → 8 → 9 → 6 → 10) is architecturally correct for the following reasons:

| Phase | Why This Position |
|-------|------------------|
| Phase 0: Infra (DB schema, Docker, migrations) | Everything depends on Postgres. Must be first. |
| Phase 2: Ingest endpoint + pipeline skeleton | Establishes the BackgroundTask pattern before any service is built into it. |
| Phase 1: Full pipeline (parse→embed→extract→resolve→edges→flashcards) | The centerpiece. Depends on Phase 0 schema being complete. |
| Phase 3: Graph API | Depends on concepts + edges written by Phase 1. |
| Phase 4: SRS + flashcard endpoints | Depends on flashcards written by Phase 1. Threshold tuning belongs here. |
| Phase 5: Quiz | Depends on mastery scores from Phase 4. |
| Phase 7: Frontend graph + study pages | Depends on Phase 3 + 4 APIs being stable. |
| Phase 8: NotchDrop integration | Depends on POST /ingest (Phase 2) being stable. Can parallelize with Phase 7. |
| Phase 9: Seed data + demo script | Requires all backend phases complete. |
| Phase 6: Polish | Last because it depends on everything. |
| Phase 10: Demo hardening | Final. |

**Key dependency chain:**
```
Phase 0 (schema) → Phase 2 (ingest skeleton) → Phase 1 (full pipeline)
                                                      ↓
                       Phase 3 (graph API) ← concepts/edges written
                       Phase 4 (SRS)       ← flashcards written
                       Phase 5 (quiz)      ← mastery written
                            ↓
                       Phase 7 (frontend)  ← APIs stable
                       Phase 8 (Swift)     ← POST /ingest stable
                            ↓
                       Phase 9 (seed)      ← full backend complete
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Building the ivfflat index before seeding
**What:** Creating the index in Alembic migration `0001_initial.py` on an empty table.
**Why bad:** ivfflat clusters existing rows. An index on an empty table is useless and won't improve query performance until `REINDEX` is run after data exists.
**Instead:** Create the index in a separate Alembic migration that runs after `seed_demo.py`, or add a `REINDEX` call at the end of `seed_demo.py`.

### Anti-Pattern 2: One SQLAlchemy session per pipeline run
**What:** Opening a single `AsyncSession` at the start of `run_pipeline()` and passing it through all 8 stages.
**Why bad:** A 60-second pipeline with one session holds a DB connection for the full duration, blocks connection pool slots, and fails on any long LLM call that exceeds the connection idle timeout.
**Instead:** Open a new session per stage (or per batch of DB writes). Use the `async with get_session() as session:` context manager inside each stage function.

### Anti-Pattern 3: Using `dagre` (original) instead of `@dagrejs/dagre`
**What:** `npm install dagre` — the original package has been unmaintained since ~2018.
**Why bad:** No TypeScript types, no ESM support, potential issues with React Flow v12's pure-ESM build.
**Instead:** `npm install @dagrejs/dagre @types/dagrejs__dagre` — the actively maintained fork with TypeScript definitions.

### Anti-Pattern 4: Course-global concept resolution (no course_id filter in ANN query)
**What:** Running the resolver without scoping to `WHERE course_id = $1` in the ANN query.
**Why bad:** "Gradient Descent" in a CS course would merge with "Gradient Descent" in a Biology course if both happened to score >0.92.
**Instead:** Always include `AND course_id = :course_id` in the resolver's `SELECT ... ORDER BY embedding <=> :query_embedding` query.

### Anti-Pattern 5: Notch edit outside the `#if CORTEX_ENABLED` guard
**What:** Directly calling `CortexDropHandler` from the tray handler without a compile-time flag.
**Why bad:** Breaks the original NotchDrop behavior when Cortex is toggled off at the settings level only (runtime toggle is not enough to restore file-shelf behavior).
**Instead:** Use compile-time `#if CORTEX_ENABLED` for structural changes; use the runtime `CortexSettings.shared.isEnabled` guard only for within-Cortex logic.

---

## Scalability Considerations

At hackathon scale (1 user, <100 sources, <10K chunks, <500 concepts), none of these are blockers. Noted for awareness:

| Concern | At demo scale | At 10K users |
|---------|--------------|--------------|
| BackgroundTasks queue depth | Fine (1 user, sequential) | Would saturate uvicorn workers; arq/celery needed |
| ivfflat lists tuning | `lists=10` is fine during dev | Rebuild index with `lists=sqrt(n)` at scale |
| Concept resolution LLM cost | Negligible | Cache tiebreaker calls; batch ANN queries |
| Poll-every-5s graph refresh | Fine for 1 user | Switch to SSE or WebSocket at meaningful scale |
| SM-2 state per card | Trivial at <10K cards | Standard SRS scale, no issue |

---

## Risk Areas

| Risk | Severity | Mitigation |
|------|----------|------------|
| Pipeline stuck on server restart (no task durability) | MEDIUM | Startup hook that marks stuck rows as error; POST /retry endpoint |
| ivfflat index built before seed data (zero recall) | HIGH | Build index in seed script, not in initial migration |
| dagre abbreviation/type mismatch with @xyflow/react v12 ESM | MEDIUM | Use `@dagrejs/dagre` with TypeScript types; test import at project setup |
| Abbreviation-based concept drift (NN vs Neural Network) | MEDIUM | Extractor prompt instructs: return full canonical name, no abbreviations |
| Concept embedding quality for short names | LOW | text-embedding-3-small handles short strings adequately; monitor after Phase 4 |
| NotchDrop upstream merge conflicts | LOW | Cortex/ subfolder minimizes diff surface; single surgical edit to one upstream file |
| LLM tiebreaker latency blocking resolver | LOW | Tiebreaker is async; UI shows status=processing during pipeline |

---

## Sources

- FastAPI BackgroundTasks official docs (fetched 2026-04-25): https://fastapi.tiangolo.com/tutorial/background-tasks/
- FastAPI deployment concepts (fetched 2026-04-25): https://fastapi.tiangolo.com/deployment/concepts/
- pgvector README (training knowledge, Aug-2025): sqrt(n) lists heuristic is canonical in project README
- React Flow / xyflow docs (training knowledge, Aug-2025): @xyflow/react v12, dagre separation
- dagrejs/dagre fork (training knowledge, Aug-2025): actively maintained vs abandoned original
- text-embedding-3-small cosine similarity space (training knowledge, Aug-2025): threshold interpretations from published RAG system literature
- Swift app module scoping (fundamental language behavior, stable): no external source needed
