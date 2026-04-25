# Technology Stack

**Project:** Cortex (student knowledge-graph + spaced-repetition second-brain)
**Researched:** 2026-04-25
**Note:** All web/CLI research tools denied in this environment. Analysis drawn from training data (cutoff August 2025). Confidence levels reflect this constraint. Items marked [VERIFY] should be checked against live package registries before pinning.

---

## Validation Summary

The spec's stack is coherent and well-chosen for a hackathon-scope, single-user, local demo. Every piece fits a recognizable 2025 pattern for AI-assisted knowledge apps. No locked choice is wrong. Several choices have non-obvious nuances documented below.

---

## Recommended Stack (Validated)

### Frontend

| Technology | Locked Version | Current Stable (Aug 2025) | Status | Notes |
|------------|---------------|--------------------------|--------|-------|
| Next.js | 14 (App Router) | 15.x is current | ACCEPTABLE — do not upgrade | Next 15 changed caching defaults and server action behavior; upgrading mid-hackathon is a trap. Pin to 14.2.x. |
| TypeScript | Latest (implied) | 5.5.x | CORRECT | 5.5 introduces isolated declarations; no breaking changes for this use case. |
| Tailwind CSS | Latest (implied) | 3.4.x | CORRECT | v4 alpha was circulating but v3 is the stable production choice. |
| shadcn/ui | Latest (implied) | Component-registry model | CORRECT | shadcn/ui is not a versioned package — it copies components into src/components/ui. No version to pin. Pin the Radix UI primitives it pulls in. |
| React Flow | v12 (implied) | 12.x | CORRECT with caveats — see below |

#### React Flow v12 vs v11 — Dagre Layout Gotcha

**Confidence: HIGH** (this change was extensively documented)

React Flow v12 introduced a significant API reshaping:

- **Package rename**: `reactflow` → `@xyflow/react`. The old `reactflow` package still exists as an alias but the canonical import is `@xyflow/react`.
- **Node data typing**: `NodeData` is now a generic. Custom node components receive `NodeProps<YourData>` not the old untyped `data` prop. This is a TypeScript-only breaking change — JavaScript users unaffected.
- **`useNodesState` / `useEdgesState`**: These hooks still exist and work as before.
- **Dagre layout**: `@dagrejs/dagre` still works with v12 the same way as v11. The pattern is unchanged — call `dagre.layout()` in a `useMemo` or `useCallback`, then set node positions. No v12-specific dagre breakage.
- **`fitView` behavior**: The `fitView` option on `<ReactFlow>` component is unchanged, but `fitViewOptions` prop placement changed slightly in some minor versions — verify the exact prop name against the v12 docs.
- **`MiniMap`, `Controls`, `Background`**: These are still named exports from `@xyflow/react`.

**Action required**: Import from `@xyflow/react`, not `reactflow`. The spec likely means the v12 package under the `@xyflow/react` name.

**Pin recommendation**: `"@xyflow/react": "^12.0.0"` — do NOT pin to exact version since the v12.x minor releases fix real bugs without breaking API.

---

### Backend

| Technology | Locked Version | Current Stable (Aug 2025) | Status | Notes |
|------------|---------------|--------------------------|--------|-------|
| FastAPI | Latest (implied) | 0.111.x–0.115.x | CORRECT | FastAPI 0.100+ is stable. The project uses standard patterns (router, background tasks, lifespan). Pin to `>=0.111,<0.116` for stability. |
| uvicorn | Latest (implied) | 0.30.x | CORRECT | Use `uvicorn[standard]` to get `websockets` and `httptools`. Even though WebSockets are out of scope, `httptools` improves HTTP/1.1 throughput. |
| SQLAlchemy | 2.0 | 2.0.30+ | CORRECT | SQLAlchemy 2.0 is the right choice. The 1.x style (implicit autocommit, `session.execute(str)`) is fully deprecated. Use `async_sessionmaker` + `AsyncSession` for all DB work with FastAPI. |
| Alembic | Latest (implied) | 1.13.x | CORRECT | Alembic 1.13 works with SQLAlchemy 2.0 models without any shims. |
| httpx | Latest (implied) | 0.27.x | CORRECT | httpx 0.27 is stable. Use `httpx.AsyncClient` for URL fetching inside FastAPI background tasks (not `requests`, which blocks the event loop). |
| pymupdf | Latest (implied) | 1.24.x | CORRECT with one note — see below |
| trafilatura | Latest (implied) | 1.x | CORRECT with failure modes — see below |

#### pymupdf Note
**Confidence: HIGH**

PyMuPDF rebranded/reorganized its import path. In version 1.24+:
- Old import: `import fitz`
- New import: `import pymupdf` (also `import fitz` still works as alias)

The package on PyPI is still `pymupdf`. Either import works, but the spec and any sample code should use `import fitz` (legacy, universally documented) or `import pymupdf` (new canonical). Both are fine. **Do not accidentally install `PyMuPDF` + `pymupdf` as separate packages** — they are the same package with two PyPI listings that can conflict.

**Pin recommendation**: `pymupdf>=1.24.0` — the 1.24 series adds native Python bindings that are faster than the 1.23 SWIG bindings.

#### trafilatura Failure Modes
**Confidence: MEDIUM** (based on well-documented community issues)

trafilatura 1.x is a strong default for article/blog extraction but has known failure modes relevant to student content:

1. **JavaScript-rendered pages**: trafilatura fetches static HTML only. Any SPA (React/Angular apps, many modern documentation sites) returns near-empty content. Mitigation: the spec's pipeline should log `extraction_length < 200 chars` as a warning and fall back to `<title>` + raw paragraph scraping with `BeautifulSoup` as a last resort.
2. **Paywalled content**: trafilatura will return the paywall prompt text, not the article. Not a hackathon concern but worth noting for seed data sourcing.
3. **arXiv PDFs via URL**: Students will drop arXiv links. trafilatura on `arxiv.org/abs/XXXX` returns abstract HTML, not the PDF. The pipeline needs to detect `arxiv.org/abs/` URLs and rewrite them to `arxiv.org/pdf/XXXX.pdf`, then route through the PDF parser instead.
4. **Wikipedia**: trafilatura on Wikipedia works well but returns the entire article, which can be 50K+ tokens. The chunking step must enforce `max_chunk_size` before embedding.
5. **YouTube / video URLs**: Returns nothing useful. Should be explicitly rejected at the ingest endpoint with a `422` error and user-facing message.

**Pin recommendation**: `trafilatura>=1.6.0` — 1.6 improved metadata extraction and encoding handling.

---

### Database

| Technology | Locked Version | Current Stable (Aug 2025) | Status | Notes |
|------------|---------------|--------------------------|--------|-------|
| PostgreSQL | 16 | 16.3 / 17 beta | CORRECT | Postgres 16 is the current LTS. Postgres 17 was in beta through mid-2025; avoid for a hackathon. |
| pgvector | Latest (implied) | 0.7.x | CORRECT with index decision — see below |

#### pgvector: ivfflat vs hnsw
**Confidence: HIGH** (this was a major announced feature in pgvector 0.6/0.7)

pgvector 0.5 added HNSW indexing. As of 0.6+, the recommendation has shifted:

**ivfflat (spec's current choice)**:
- Build time: Fast (seconds for small datasets)
- Memory: Low
- Query accuracy: Requires `lists` tuning — with the wrong `lists` value, recall degrades
- Query speed: Fast after training
- Limitation: **Requires a training phase** — you must `SET ivfflat.probes` and the index is built against existing data. An empty table produces a useless index. Must be created AFTER bulk data load.

**hnsw**:
- Build time: Slower (but still fast at hackathon scale — under 1s for <10K vectors)
- Memory: Higher (graph structure in RAM)
- Query accuracy: Excellent out of the box, no tuning required
- Query speed: Faster than ivfflat at equivalent recall
- Key advantage: **No training phase required** — works correctly on an empty table and as rows insert

**Verdict for Cortex**: For a hackathon with <10K concept vectors, **hnsw is the better choice**. The spec choosing ivfflat is a valid conservative default but has one real gotcha: if you create the ivfflat index on an empty `concepts` table at migration time (which is the natural Alembic workflow), it will be poorly trained and queries will have degraded recall until you `REINDEX` after data load. The hnsw index avoids this entirely.

**Recommendation**: Switch the planned index from ivfflat to hnsw. The SQL is:
```sql
CREATE INDEX ON concepts USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```
Set `SET hnsw.ef_search = 40` at query time for the cosine similarity lookups in concept resolution. At hackathon scale this adds zero perceptible overhead.

**If ivfflat is kept** (e.g., for spec fidelity): create it in a separate Alembic migration that runs AFTER the seed script, not in the initial schema migration. Use `lists = 10` for small datasets (rule of thumb: `sqrt(row_count)` up to 100).

---

### AI / ML

| Technology | Locked Choice | Status | Notes |
|------------|--------------|--------|-------|
| Anthropic claude-sonnet-4-5 | claude-sonnet-4-5 | CORRECT | This is the spec's exact model string. claude-sonnet-4-5 is a real Anthropic model identifier. Use `anthropic>=0.25.0` SDK. Structured output via tool-use / `response_format` for JSON extraction; do not parse free-text JSON with regex. |
| OpenAI text-embedding-3-small | 1536-dim | CORRECT with note | text-embedding-3-small supports 1536 (full) or truncated dimensions via `dimensions` param. The spec correctly identifies 1536. Pin `openai>=1.30.0` SDK — the v1.x client (not the legacy 0.x) is required. |

#### SM-2 Algorithm Correctness
**Confidence: HIGH** (SM-2 is a fixed published algorithm with well-known reference implementation)

The SM-2 algorithm published by Piotr Wozniak in 1987 has these exact rules:

```
Grades: 0 (blackout), 1 (incorrect, close), 2 (incorrect, easy), 
        3 (correct, hard), 4 (correct, hesitation), 5 (correct, easy)

Spec maps to: 1=Again, 3=Hard, 4=Good, 5=Easy (skipping 0 and 2)

ease_factor update:
  new_EF = EF + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
  Clamp: EF must never go below 1.3

interval update:
  if grade < 3: reset (repetitions=0, interval=1 day)
  elif repetitions == 0: interval = 1
  elif repetitions == 1: interval = 6
  else: interval = round(interval * EF)

due_at = now + timedelta(days=interval)
repetitions increments on grades >= 3
```

**Spec's grade mapping (1/3/4/5)** is valid — it skips the two "incorrect answer" grades (0, 2) and maps the four UI buttons to the four most meaningful SM-2 states. This is a common simplification used by Anki and others.

**Common implementation bugs to watch for**:
1. Not clamping EF below 1.3 → intervals collapse to 1 day forever after enough "Hard" grades
2. Applying the EF update even on grade < 3 (should reset, not update)
3. Using `datetime.now()` without timezone awareness → `due_at` comparisons break if server TZ ever changes. Use `datetime.utcnow()` or `datetime.now(UTC)` and store as UTC.
4. `round()` in Python 3 uses banker's rounding (round-half-to-even). For intervals this is inconsequential but worth knowing.

---

### Swift / macOS Client

| Technology | Locked Choice | Status | Notes |
|------------|--------------|--------|-------|
| Swift / SwiftUI | macOS, NotchDrop fork | CORRECT | SwiftUI on macOS 14+ (Sonoma) is stable for the UI patterns needed. The notch panel itself uses AppKit (`NSPanel`) under the hood in NotchDrop — preserve that, don't convert to SwiftUI window. |

**Key gotcha**: `NSItemProvider` for drag-and-drop has two distinct APIs — the deprecated synchronous API and the modern async `loadDataRepresentation(forTypeIdentifier:)`. NotchDrop already uses the modern API. When adding Cortex file handling, match the existing pattern exactly. Do not mix the two APIs in the same drop handler.

**URLSession for Swift async**: Swift 5.5+ `URLSession.data(for:)` is the correct async API. Do NOT use `URLSession.dataTask(with:completionHandler:)` in Swift concurrency contexts — it does not propagate cancellation properly.

---

### Infrastructure

| Technology | Locked Choice | Status | Notes |
|------------|--------------|--------|-------|
| Docker Compose (Postgres + pgvector only) | Latest Compose V2 | CORRECT | Use `pgvector/pgvector:pg16` as the Docker image — it ships Postgres 16 + pgvector pre-installed. Do NOT use the base `postgres:16` image and install pgvector via init script; the init script approach fails silently in some Compose setups. |

**Recommended `docker-compose.yml` image**: `pgvector/pgvector:pg16` (official image, maintained by the pgvector project).

---

## Alternatives Considered (Why the Spec's Choices Are Correct)

| Category | Spec Choice | Most Common Alternative | Why Spec Choice Wins |
|----------|-------------|------------------------|----------------------|
| Vector DB | pgvector | Pinecone, Weaviate, Qdrant | No additional infra service; Postgres already running; hackathon scale doesn't need a dedicated vector DB |
| ORM | SQLAlchemy 2.0 | Tortoise ORM, Prisma (Python) | SQLAlchemy 2.0 async is mature, well-documented, has Alembic; Tortoise is solid but less documentation |
| PDF parsing | pymupdf | pdfplumber, pypdf | pymupdf is the fastest and handles malformed PDFs best; pdfplumber is slower; pypdf misses layout context |
| Web extraction | trafilatura | newspaper3k, readability-lxml | trafilatura outperforms newspaper3k on modern sites; readability-lxml is unmaintained |
| LLM | Claude Sonnet | GPT-4o | Either works; Claude structured outputs via tool-use are clean; vision OCR quality is comparable |
| Embeddings | text-embedding-3-small | text-embedding-3-large, Cohere | 3-small is 5x cheaper, 0.5x slower, and adequate for 1536-dim cosine similarity at <10K vectors |
| Frontend | Next.js 14 App Router | Remix, Vite+React SPA | App Router RSC patterns suit a mostly-read-heavy graph viewer; no need for Remix's form primitives |

---

## Installation Reference

```bash
# Python backend (pin these in requirements.txt)
fastapi>=0.111.0,<0.116.0
uvicorn[standard]>=0.30.0
sqlalchemy>=2.0.30,<2.1.0
alembic>=1.13.0
asyncpg>=0.29.0          # async Postgres driver for SQLAlchemy
psycopg2-binary>=2.9.9   # needed by Alembic for sync migrations
httpx>=0.27.0
trafilatura>=1.6.0
pymupdf>=1.24.0
anthropic>=0.25.0
openai>=1.30.0
pgvector>=0.3.0          # Python pgvector type adapter for SQLAlchemy

# Frontend (package.json additions)
# @xyflow/react ^12.0.0   (NOT "reactflow" — wrong package name for v12)
# @dagrejs/dagre ^1.0.0
# shadcn/ui    (via `npx shadcn-ui init`, not npm install)
```

---

## Version Pinning Recommendations

| Package | Pin Strategy | Reason |
|---------|-------------|--------|
| fastapi | `>=0.111,<0.116` | Patch-safe within minor; avoid accidental 0.116 breaking changes |
| sqlalchemy | `>=2.0.30,<2.1` | 2.1 may ship with deprecation cleanups |
| openai | `>=1.30.0` | 1.x client is stable; < 1.0 was entirely different API |
| anthropic | `>=0.25.0` | Tool-use structured output API stabilized in 0.25 |
| pymupdf | `>=1.24.0` | 1.24 new bindings; 1.23 has slower SWIG bridge |
| @xyflow/react | `^12.0.0` | Semver-safe within v12 |
| next | `14.2.x` | Do NOT upgrade to 15 during hackathon |
| pgvector Docker | `pgvector/pgvector:pg16` | Locked to pg16 slot; auto-updates pgvector minor versions |

---

## What NOT to Use

| Avoid | Use Instead | Why |
|-------|-------------|-----|
| `reactflow` (npm package) | `@xyflow/react` | v12 canonical package name; `reactflow` is a deprecated alias |
| `requests` in FastAPI handlers | `httpx.AsyncClient` | `requests` blocks the event loop; kills FastAPI's async advantage |
| `session.execute("raw SQL string")` in SQLAlchemy 2.0 | `session.execute(select(Model))` | Raw string execution was removed in 2.0 — use `text()` wrapper at minimum |
| `postgres:16` Docker image | `pgvector/pgvector:pg16` | Base image requires manual pgvector extension install; official image has it pre-built |
| `datetime.now()` (naive) | `datetime.now(timezone.utc)` | Naive datetimes cause subtle `due_at` comparison bugs |
| ivfflat index on empty table | hnsw OR deferred ivfflat migration | ivfflat built on empty table has poor recall until REINDEX after data load |
| `import pymupdf` + `import fitz` in same file | Pick one (prefer `import fitz`) | Both work but mixing can cause confusion; `fitz` is more universally shown in docs |
| Next.js 15 | Next.js 14.2.x | v15 changed caching semantics and server action behavior; unnecessary risk |
| `asyncio.run()` inside FastAPI route handlers | `BackgroundTasks` or `asyncio.create_task()` | `asyncio.run()` creates a new event loop and deadlocks inside an async context |

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| React Flow v12 package rename (`@xyflow/react`) | HIGH | Announced publicly in v12 release; widely documented |
| pgvector hnsw recommendation over ivfflat | HIGH | Feature added in pgvector 0.5, widely benchmarked; index-on-empty-table gotcha is well-documented |
| SM-2 algorithm correctness | HIGH | Published algorithm with fixed spec; bugs are in implementation, not the spec |
| FastAPI / SQLAlchemy 2.0 patterns | HIGH | Stable, well-documented patterns |
| pymupdf 1.24 import change | HIGH | Official PyMuPDF migration guide published |
| trafilatura failure modes | MEDIUM | Community-documented; exact version as of April 2026 requires [VERIFY] |
| Next.js 14 vs 15 caching changes | HIGH | Well-documented Next.js 15 migration guide |
| claude-sonnet-4-5 model availability | MEDIUM | Model string from spec; verify against Anthropic API docs that this exact ID is live [VERIFY] |
| openai SDK 1.x vs 0.x | HIGH | Migration was a major breaking change; 1.x is current |
| Current package versions (exact patch numbers) | LOW | Requires live PyPI/npm check — [VERIFY ALL] before pinning in requirements.txt |

---

## Sources

All findings from training data (knowledge cutoff August 2025). Live verification blocked.

- pgvector HNSW: https://github.com/pgvector/pgvector (README, Indexing section)
- React Flow v12 migration: https://reactflow.dev/learn/troubleshooting/migrate-to-v12
- SM-2 algorithm: https://www.supermemo.com/en/blog/application-of-a-computer-to-improve-the-results-obtained-in-working-with-the-supermemo-method (original 1987 spec)
- PyMuPDF 1.24 changes: https://pymupdf.readthedocs.io/en/latest/changes.html
- SQLAlchemy 2.0 migration: https://docs.sqlalchemy.org/en/20/changelog/migration_20.html
- OpenAI Python SDK v1.0 migration: https://github.com/openai/openai-python/discussions/742
- Next.js 15 upgrade guide: https://nextjs.org/docs/app/building-your-application/upgrading/version-15
