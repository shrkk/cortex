---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: Phase 4 — Flashcards, Struggle & Quiz
current_plan: Plan 0 of 4 (not started)
status: complete
last_updated: "2026-04-26T01:10:39.323Z"
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 25
  completed_plans: 16
  percent: 64
---

# Project State: Cortex

*This file is the project's memory. Updated at every phase transition and plan completion.*

---

## Project Reference

**Core value:** A student drops content into the notch → Cortex automatically builds a course-rooted knowledge graph and generates ready-to-study flashcards — zero manual effort between "I have this PDF" and "I'm studying these concepts."

**Milestone:** v1 (hackathon demo)
**Surfaces:** Swift macOS notch app (Cortex Drop) + FastAPI backend (Cortex API) + Next.js frontend (Cortex Web)

---

## Current Position

**Current phase:** Phase 2 — Ingest + Parsing + Notch
**Current plan:** Plan 0 of 8 (not started)
**Status:** Ready to execute
**Last action:** Phase 2 planning complete — 2026-04-25

```
Progress: [████████████████████] 100% (Phase 1)

Phase 1: Infrastructure          [x] COMPLETE — 5/5 plans complete
Phase 2: Ingest + Parsing + Notch [~] PLANNED — 8/8 plans ready
Phase 3: Extraction, Resolution & Edges [~] PLANNED — 4/4 plans ready
Phase 4: Flashcards, Struggle & Quiz [~] PLANNED — 4/4 plans ready
Phase 5: Graph API               [ ] Not started
Phase 6: Frontend                [ ] Not started
Phase 7: Demo Readiness          [ ] Not started
```

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total | 7 |
| Phases complete | 0 |
| Plans total | 5 (Phase 1) |
| Plans complete | 5 |
| Requirements mapped | 71/71 |
| Requirements complete | 5/71 (INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05) |
| Phase 1 duration | ~20 min total |
| Phase 1 tests | 5/5 passing |

---

## Accumulated Context

### Locked Decisions

| Decision | Rationale |
|----------|-----------|
| No SRS scheduling | Flashcards are flip-only graph nodes; no due dates, ease factors, or repetitions (v2) |
| No mastery scoring | Struggle signals feed quiz generation only; mastery is v2 scope |
| No grading on flashcard flip | Pure display toggle — no DB write on "Show Answer" |
| Quiz node hangs off course root | Not connected to individual concepts (QUIZ-01) |
| Course assignment is dynamic | Pre-flight `/courses/match` + inline CortexCourseTab, no static course ID in settings |
| `@xyflow/react` not `reactflow` | React Flow v12 renamed the package; `reactflow` is deprecated alias |
| `@dagrejs/dagre` not `dagre` | Original `dagre` unmaintained; ESM incompatibility causes silent layout failure |
| `pgvector/pgvector:pg16` Docker image | Base `postgres:16` requires manual pgvector install; official image has it pre-built |
| `pydantic-settings==2.0.0` separate package | Pydantic v2 extracted BaseSettings into its own package — `from pydantic import BaseSettings` fails in v2 |
| `Vector(1536)` explicit dimension | Dimensionless `Vector()` fails silently at query time; must match OpenAI text-embedding-3-small 1536-dim output |
| hnsw index for concepts table | ivfflat on empty table has near-zero recall; hnsw works incrementally |
| ivfflat for chunks deferred | Create after seed data is loaded, not in initial migration |
| Alembic migration hand-written | autogenerate skips `pgvector.sqlalchemy.Vector` columns silently |
| FastAPI startup hook resets `processing` → `pending` | Guards against silent task loss on uvicorn --reload |
| `source_metadata` / `edge_metadata` Python attribute names | SQLAlchemy Declarative API reserves 'metadata'; explicit `mapped_column("metadata", JSON)` preserves DB column name |
| alembic.ini uses psycopg2 sync URL | asyncpg is async-only; synchronous migration runner raises RuntimeError if asyncpg URL is used |
| CORS allows missing Origin header | Swift URLSession sends no Origin; `allow_origins=["*"]` for local dev |
| Session-per-stage in pipeline | Single session across 8 stages exhausts connection pool; fresh session per stage |
| pg_insert ON CONFLICT DO NOTHING for seed | Dialect-specific upsert clearer than ORM merge() for integer PK idempotency |
| Course idempotency via count check | SELECT COUNT(*) per user_id simpler than per-title conflict; sufficient for Phase 1 minimal seed |

### Critical Pitfalls (do not forget)

1. **UTI ordering in NSItemProvider**: check `public.png`/`public.jpeg` BEFORE `public.file-url`; browser image drag gives temp file URL that disappears seconds after drop
2. **Alembic Vector columns**: always hand-write the initial migration; test on `docker compose down -v && docker compose up -d`
3. **dagre at origin**: copy official xyflow.com v12 dagre example verbatim; `nodeTypes` defined outside component body; `setTimeout(fitView, 0)` after setNodes
4. **extraction_cache invalidation**: `TRUNCATE extraction_cache` after every extraction prompt edit
5. **Concept resolution scope**: resolver cosine query MUST include `AND course_id = :course_id`
6. **Demo seed variance**: verify mastery distribution with `SELECT round(mastery_score::numeric,1), count(*) FROM concepts GROUP BY 1` — must NOT be uniform at 0.5 (though mastery is v2, struggle signal variance IS required)

### Todos

- [ ] Verify `claude-sonnet-4-5` model ID is live against Anthropic API before Phase 3
- [ ] Run `npm info @xyflow/react` to confirm latest v12 stable before pinning
- [ ] After Phase 3: manually inspect 10 concept nodes in psql; tune resolution thresholds if over/under-merging
- [ ] After Phase 7 seed: verify struggle signal distribution (≥ 3 with signals, ≥ 3 without)

### Blockers

*None currently.*

---

## Session Continuity

**Last session:** 2026-04-26T00:14:33.708Z
**Next action:** Execute Phase 2 (Ingest + Parsing + Notch)
**Open questions:** None

---

*State initialized: 2026-04-25*
*Last updated: 2026-04-25*
