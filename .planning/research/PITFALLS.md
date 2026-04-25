# Domain Pitfalls

**Domain:** Knowledge-graph + LLM extraction + SRS — macOS notch drop zone, FastAPI pipeline, pgvector, React Flow
**Researched:** 2026-04-25
**Confidence:** HIGH for pitfalls grounded in well-documented API behaviors; MEDIUM for demo-specific failure modes

---

## Critical Pitfalls

Mistakes that cause rewrites, silent data corruption, or demo-killing failures.

---

### Pitfall C-1: NSItemProvider UTI ordering — file URL shadows image data

**What goes wrong:** When a user drags an image from a browser, the pasteboard often advertises both `public.file-url` (a temp file on disk) and `public.image` (raw pixel data). If the `onDrop` handler iterates providers in declaration order and picks the first matching UTI, it can resolve the URL conformance before the image conformance. The result is a `file://` URL pointing to a `/private/var/folders/…` temp file that disappears seconds after the drag ends. `CortexIngest` sends a dead URL to the backend; the backend tries to fetch it and gets a 404 or file-not-found.

**Why it happens:** `NSItemProvider.loadItem(forTypeIdentifier:)` is asynchronous and results arrive out of order. Code written as `if provider.hasItemConformingToTypeIdentifier(kUTTypeFileURL)` then `else if … image` will always prefer the URL path. Safari additionally wraps image drags in `com.apple.webarchive` which confounds simple type checks.

**Consequences:** Image drops silently create failed source rows with no meaningful content. The pipeline records `status=error` but the user sees nothing wrong in the notch.

**Prevention:**
- Declare UTI priority explicitly: check `public.image` / `public.png` / `public.jpeg` BEFORE `public.file-url`. Only fall through to file-url if no image type resolves.
- After resolving a file-url, stat the path immediately; if it does not exist, try the image provider as fallback.
- Log all advertised UTI types from every provider to `os.log` at debug level during Phase 1. This log is the fastest diagnostic.

**Warning signs:** Drop handler runs, status pill shows "Sent", backend receives a URL with a `/var/folders` path, immediately returns 422 or 500.

**Phase:** Address in Phase 1 (NotchDrop fork / Cortex Drop).

---

### Pitfall C-2: NSEvent global monitor loses key events when notch is not front

**What goes wrong:** `NSEvent.addGlobalMonitorForEvents(matching:)` cannot intercept events that a different application has already consumed. For `⌘V`, if the focus is on a browser text field, the browser handles the keydown first and the global monitor never fires. The clipboard paste path in `CortexIngest.handleClipboard()` therefore only works reliably when no other app's text input is focused.

**Why it happens:** Global monitors observe the event stream after delivery to the focused application; `NSEvent.addLocalMonitorForEvents` only fires when the monitor's own app is key. There is no documented way to intercept `⌘V` from another app's text input without Accessibility entitlements.

**Consequences:** The `⌘V` paste path works during a controlled demo (user switches focus to the notch widget first) but fails unexpectedly if the user tries to paste while still in a browser window.

**Prevention:**
- The notch panel must become the key window before clipboard handling is attempted. Verify the notch widget calls `makeKeyAndOrderFront` or equivalent on open.
- Add a note to the demo script: "Click the notch zone first, then ⌘V."
- Do not rely on the global monitor for `⌘V` in the background; scope the clipboard-paste feature to "notch is visible/active."

**Warning signs:** Paste works in Xcode simulator/preview but not when a browser is in front. The `handleClipboard` function is never called.

**Phase:** Address in Phase 1; add demo-script note in Phase 10.

---

### Pitfall C-3: Safari vs Chrome image copy — different pasteboard type sets

**What goes wrong:** Chrome (on macOS) writes `public.png` to the pasteboard when you copy an image. Safari writes `com.compuserve.gif` or `public.tiff` depending on the source image format, and also adds `com.apple.webarchive`. Code that only checks for `public.png` will silently drop Safari image copies.

**Why it happens:** Each browser constructs its own pasteboard representation. Safari follows a "fidelity hierarchy" that puts web archive above raw image bytes.

**Consequences:** `⌘V` of an image copied from Safari produces an empty paste event or falls through to string handling and creates a malformed text source.

**Prevention:**
- Check for this full ordered list: `public.png`, `public.jpeg`, `public.tiff`, `com.compuserve.gif`. Accept the first that resolves.
- Log `NSPasteboard.general.types` unconditionally when `handleClipboard` fires. This single log line diagnoses 100% of cross-browser issues.

**Warning signs:** Image paste from Safari produces a source with `source_type=text` containing partial HTML, or produces no source at all.

**Phase:** Address in Phase 1.

---

### Pitfall C-4: FastAPI BackgroundTasks — task silently dropped on shutdown

**What goes wrong:** `BackgroundTasks` runs inside the ASGI event loop on the same worker process as uvicorn. When uvicorn receives SIGTERM (e.g., `Ctrl-C` during development, or a crash), it cancels pending coroutines. Any pipeline task that has not yet completed is discarded with no error, no retry, and no record. The source row stays in `status=processing` forever.

**Why it happens:** FastAPI's `BackgroundTasks` uses Starlette's implementation, which schedules tasks via `asyncio.ensure_future` within the request lifecycle. There is no persistence layer, queue, or acknowledgement system.

**Consequences:** During iterative development (frequent `uvicorn --reload` restarts), every in-flight extraction is silently dropped. The DB accumulates `status=processing` zombie rows that never resolve. Seed script may appear to succeed but produce empty concept graphs.

**Prevention:**
- Implement a startup reconciliation step: on `app.on_event("startup")`, query for any source rows with `status=processing` and reset them to `status=pending` (re-queue). This makes restart-safe.
- Do not kill uvicorn with `-9` (SIGKILL) during development; use `Ctrl-C` (SIGTERM) to give the loop time to drain in-progress awaits.
- Log `source_id` and pipeline stage at every major step so partial progress is visible.

**Warning signs:** Seed script completes without error, but `SELECT status, count(*) FROM sources GROUP BY status` shows rows stuck in `processing`. Concept count is zero after a reload.

**Phase:** Address in Phase 2 (Backend pipeline scaffolding).

---

### Pitfall C-5: SQLAlchemy / asyncpg connection not released inside BackgroundTask

**What goes wrong:** If the background pipeline function opens a DB session via `async with AsyncSession(engine) as session` correctly, this is fine. But if the session is opened outside the `async with` block (e.g., passed in from the request scope, or stored as a module-level variable), it may not be closed when the task ends. Over many pipeline runs (especially during seeding with 20–50 chunks), the connection pool (default size 5) exhausts and new requests hang indefinitely waiting for a connection.

**Why it happens:** SQLAlchemy's `AsyncSession` is not thread-safe and is not designed to be shared across request/task boundaries. FastAPI's dependency-injected sessions use `yield`-based cleanup; that cleanup does not execute for background tasks.

**Consequences:** After running the seed script, the app becomes unresponsive. All `/ingest` calls hang. Only a uvicorn restart recovers.

**Prevention:**
- In every background pipeline function, open a fresh session with `async with AsyncSession(engine) as session:` at the task entry point. Never pass a request-scope session into a background task.
- Set `pool_size=10, max_overflow=5` on the engine for development to increase headroom.
- Use `pool_pre_ping=True` to catch stale connections.

**Warning signs:** API stops responding after seeding; `SELECT count(*) FROM pg_stat_activity WHERE state = 'idle in transaction'` shows many rows.

**Phase:** Address in Phase 2.

---

### Pitfall C-6: Alembic autogenerate does not detect pgvector `Vector` type

**What goes wrong:** When you run `alembic revision --autogenerate`, Alembic compares the SQLAlchemy model metadata against the live DB schema. The `pgvector.sqlalchemy.Vector` type is not a built-in SQLAlchemy type. If the `compare_type` function in `env.py` is not configured to handle it, Alembic either (a) generates a migration that tries to `ALTER COLUMN … TYPE vector(1536)` even when the column already exists with the correct type, or (b) generates a no-op migration that never creates the column at all on a fresh DB.

**Why it happens:** Alembic's autogenerate relies on SQLAlchemy type reflection. Postgres reports the column type as `USER-DEFINED` or `vector`, which does not map to the Python `Vector` class without a custom `TypeDecorator` or `include_symbol` configuration.

**Consequences:** `alembic upgrade head` on a fresh database silently skips creating the embedding columns. Embedding storage fails at runtime with `column "embedding" does not exist`.

**Prevention:**
- Manually write the initial migration rather than relying on autogenerate for the `Vector` columns. Use `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` at the top, then `op.add_column(..., sa.Column("embedding", Vector(1536)))`.
- Pin the `CREATE EXTENSION` call before any table creation in the migration file.
- Test migration on a clean database (`docker compose down -v && docker compose up -d`) before Phase 3.

**Warning signs:** `alembic upgrade head` completes without error but `\d chunks` in psql does not show an `embedding` column.

**Phase:** Address in Phase 2 (first migration) and verify in Phase 3 (embedding pipeline).

---

### Pitfall C-7: pgvector ivfflat index is useless (or harmful) on small datasets

**What goes wrong:** An `ivfflat` index with `lists=100` (the pgvector README default) requires at least `lists * 3 = 300` rows in the table for the index planner to use it. Below that threshold, the Postgres query planner will always prefer a sequential scan — but only if `enable_indexscan` is on (the default). If `enable_indexscan` is accidentally set to `off`, the planner is forced to use the index, which on a near-empty table produces wildly inaccurate approximate nearest-neighbor results (it probes only the closest IVF partition and misses most vectors).

**Why it happens:** IVF partitions are built at `CREATE INDEX` time from the existing data. With fewer rows than `lists`, multiple partitions are empty; probing `probes=10` partitions out of 100 when most are empty means most true neighbors are never examined.

**Consequences:** Concept resolution produces near-zero cosine similarity scores for embeddings that should match. New concepts are created for every chunk variant of the same concept (e.g., "Gradient Descent", "gradient descent", "gradient-descent method" all become separate nodes). The graph explodes with duplicates.

**Prevention:**
- During development and demo (< 500 rows), skip the ivfflat index entirely. Use `SELECT … ORDER BY embedding <=> $1 LIMIT 1` — sequential scan on 500 rows of 1536-dim vectors completes in < 100ms.
- If you do create an ivfflat index, use `lists=10` for development scale and only index after the seed data is loaded.
- Never set `enable_indexscan = off` globally; if needed for a specific query, wrap in a transaction and reset immediately.

**Warning signs:** Concept deduplication is not working (many near-duplicate nodes in the graph). Cosine similarity scores between clearly similar concepts return < 0.5.

**Phase:** Address in Phase 3 (embedding pipeline) and Phase 4 (concept resolution).

---

### Pitfall C-8: Embedding model dimension mismatch — wrong model silently truncates or errors

**What goes wrong:** `text-embedding-3-small` outputs 1536 dimensions. `text-embedding-3-large` outputs 3072. `text-embedding-ada-002` outputs 1536 but with a different vector space. If any code path uses a different model (e.g., a copy-paste from a `ada-002` example, or accidentally passing `model="text-embedding-3-large"`), the stored embedding has 3072 dimensions. The `Vector(1536)` column rejects it with a Postgres error. If the Vector column was declared without a dimension constraint (`Vector()` instead of `Vector(1536)`), it silently stores the wrong-sized vector, and cosine similarity comparisons between 1536-dim and 3072-dim vectors will fail or return nonsense.

**Why it happens:** The OpenAI Python SDK does not enforce model/dimension consistency. The model name is passed as a string constant that is easy to typo or inherit from an example snippet.

**Consequences:** Embedding insertion errors crash the pipeline for that chunk, leaving the source stuck in `status=processing`. Or, if the column lacks a dimension constraint, mixed-dimension vectors cause KNN queries to error at query time.

**Prevention:**
- Declare the column as `Vector(1536)` (with explicit dimension) — Postgres will reject any insert with the wrong dimension at the DB layer.
- Define a single module-level constant `EMBEDDING_MODEL = "text-embedding-3-small"` and `EMBEDDING_DIM = 1536`. Import this constant everywhere; never repeat the model name as a string literal.
- Assert `len(embedding) == EMBEDDING_DIM` before every insert.

**Warning signs:** Pipeline errors with `ERROR: expected 1536 dimensions, not 3072` or `wrong number of dimensions`.

**Phase:** Address in Phase 3 (embedding pipeline).

---

### Pitfall C-9: Claude JSON extraction — invalid JSON despite instructions, and hallucination patterns

**What goes wrong:**

**Invalid JSON:** Claude (claude-sonnet-4-5 and earlier) can produce invalid JSON in two specific conditions: (1) when the content contains code blocks with backtick fences inside the JSON string values — the model sometimes escapes them inconsistently, producing `"example": "use \`x\`"` with a bare backtick breaking the string; (2) when the context window is near-full and the response is cut mid-stream, producing truncated JSON. Using `tool_use` / forced tool response (Anthropic's structured output mode) virtually eliminates case (1) but not case (2).

**Hallucination patterns:** Concept extraction hallucination is domain-specific. The most common patterns:
- **Concept inflation**: Claude extracts generic study-skill concepts ("Problem Solving", "Critical Thinking") that are not in the source material. These concepts appear in every course and pollute the graph.
- **Title case drift**: The spec requires "Title Case, singular" concepts. Claude will sometimes return plural ("Support Vector Machines" instead of "Support Vector Machine") or acronym-only ("SVM") despite instructions, causing resolution to create duplicate nodes.
- **Gotcha invention**: When asked for "gotchas" in flashcard generation, Claude invents plausible-sounding but incorrect gotchas for topics it knows well from training, not from the source material.

**Consequences:** Hallucinated concepts create orphaned nodes in the graph with no source citations. Duplicate concepts (SVM vs Support Vector Machine) fragment mastery scores. Invented gotcha flashcards actively mislead students.

**Prevention:**
- Use `tool_use` with a strict JSON Schema for all extraction calls — this eliminates most malformed JSON. Define the schema with `additionalProperties: false` and enumerate allowed fields.
- Add a post-extraction validator: if `json.loads` fails, retry once with a "fix this JSON" prompt; on second failure, record `status=error` for that chunk (do not crash the pipeline).
- Include a negative instruction in the concept extraction prompt: "Do not extract generic study skills, metacognitive concepts, or acronym-only concepts. Extract only domain concepts explicitly stated in the text."
- After Phase 4, manually inspect 10 concept nodes from the seed data. If > 2 are clearly hallucinated, tighten the prompt.

**Warning signs:** Graph contains nodes like "Problem Solving", "Analysis", "Understanding". Multiple nodes for the same concept with slightly different names.

**Phase:** Address prompt engineering in Phase 4 (concept extraction); validate in Phase 4 manual inspection step.

---

### Pitfall C-10: React Flow v12 — dagre is no longer bundled; API changed for layouted graphs

**What goes wrong:** React Flow v11 had a separate `@dagrejs/dagre` peer dependency that the community commonly used via the `dagre` npm package with direct `node.position` mutation. React Flow v12 introduced `@xyflow/react` (the rename) and the recommended layout approach shifted: you must now call `fitView()` after layout, and the `node.positionAbsolute` field that v11 computed internally is now removed from the public API. Community examples from 2023 that mutate `node.position` inside a `useEffect` then call `setNodes` still work, but the `positionAbsolute` references in those examples throw TypeScript errors under the v12 types.

More critically: `dagre` (the original npm package) is in maintenance mode. `@dagrejs/dagre` is the maintained fork. The two have an incompatible import path. Using `import dagre from 'dagre'` with React Flow v12 type definitions often causes a `dagre.layout is not a function` error because the default export changed.

**Why it happens:** The React Flow / xyflow team renamed and refactored their package. The `dagre` layout integration was never first-party; it relied on the community examples in the docs which were updated for v12 but not all StackOverflow/blog answers caught up.

**Consequences:** The graph renders with all nodes stacked at `{x:0, y:0}`. Layout appears to run (no error) but positions are not applied to the React Flow node state, so every node overlaps at the origin.

**Prevention:**
- Use `@dagrejs/dagre` (not `dagre`). Import as `import * as dagre from '@dagrejs/dagre'`.
- After computing positions, call `setNodes(layoutedNodes)` and immediately follow with `setTimeout(() => { reactFlowInstance.fitView() }, 0)` — the timeout allows one render cycle for React Flow to measure node dimensions before fitting.
- Copy the official React Flow v12 dagre example verbatim (from xyflow.com/examples) as the starting point; do not adapt a v11 example.

**Warning signs:** All nodes render at the same position, overlapping. No JavaScript error, but the graph is a pile of nodes.

**Phase:** Address in Phase 5 (frontend graph view).

---

### Pitfall C-11: React Flow performance degradation above ~150 nodes without memoization

**What goes wrong:** React Flow re-renders every node component on every state change by default. With 100+ concept nodes and the graph polling every 5 seconds, each poll triggers a `setNodes` call which re-renders all 100+ node components. If the custom `ConceptNode` component is not wrapped in `React.memo`, and if the `nodeTypes` object is not defined outside the component (or memoized with `useMemo`), every poll cycle re-mounts all nodes. At 150 nodes, this causes visible jank (200–400ms render cycles).

**Why it happens:** React Flow docs note that `nodeTypes` must be stable (defined outside the component or memoized). A common mistake is `const nodeTypes = { concept: ConceptNode }` defined inside the parent component body, causing React Flow to treat every render as a new node type registration.

**Consequences:** Graph becomes unresponsive during the demo, especially right after a live drop when the 5s poll is active and new nodes are being added. Worst case: Chrome tab hangs.

**Prevention:**
- Define `nodeTypes` and `edgeTypes` as module-level constants outside any React component.
- Wrap `ConceptNode` with `React.memo`. Only pass primitive props (strings, numbers) to it, not object references.
- If node count will exceed 100, enable React Flow's `onlyRenderVisibleElements` prop.

**Warning signs:** Chrome DevTools Performance tab shows >16ms per frame during graph interaction. `console.log` inside `ConceptNode` fires on every poll even for nodes that did not change.

**Phase:** Address in Phase 5 (frontend graph view).

---

## Moderate Pitfalls

### Pitfall M-1: Concept resolution threshold tuning — 0.92/0.80 are starting points, not gospel

**What goes wrong:** The spec correctly notes 0.92 and 0.80 are starting points. In practice, short technical concept titles (3–5 tokens) cluster very tightly in the `text-embedding-3-small` space — "Gradient Descent" and "Stochastic Gradient Descent" can have cosine similarity of 0.94, which would merge them into one concept when they should be separate.

**Prevention:** After Phase 4, inspect the concept table. If distinct concepts are being merged (check source citations span unrelated topics), raise the merge threshold to 0.95. If trivial duplicates (plural vs singular) are NOT being merged, lower to 0.90. Spec already calls for manual DB inspection at this phase — actually do it.

**Warning signs:** Fewer concepts than expected after seeding (over-merging), or duplicate nodes with nearly identical names (under-merging).

**Phase:** Phase 4 tuning step.

---

### Pitfall M-2: extraction_cache invalidation on prompt change

**What goes wrong:** The extraction cache is keyed on `(chunk_hash, model_version)`. If the extraction prompt is changed (e.g., fixing a hallucination issue by tightening instructions), old cached results are still served because the prompt text is not part of the cache key. This is fine for production stability but causes confusion during development: prompt fixes appear to have no effect.

**Prevention:**
- During development, truncate the `extraction_cache` table after every prompt change: `TRUNCATE extraction_cache;`.
- Consider adding a `prompt_hash` to the cache key for development; document that this should be removed or pinned for production.

**Warning signs:** Prompt change has no effect on extracted concepts. Old hallucinated concepts still appear after re-running the pipeline.

**Phase:** Phase 4 development workflow; document in README.

---

### Pitfall M-3: Content-hash deduplication blocks re-processing after fixing extraction bugs

**What goes wrong:** `content_hash` deduplication is designed to prevent re-ingesting the same PDF. But during development, when extraction bugs are discovered and fixed, the developer wants to re-process the same PDF with the new pipeline. The hash check prevents this — `POST /ingest` returns the existing source row without re-running extraction.

**Prevention:**
- Implement a `force=true` query parameter on `POST /ingest` that bypasses the hash check. Only needed for development; document it.
- Alternatively: `DELETE FROM sources WHERE content_hash = $1` then re-drop.

**Warning signs:** Bug fix deployed, same PDF dropped again, pipeline does not re-run, old (buggy) concepts remain.

**Phase:** Phase 2; add `force` flag early.

---

### Pitfall M-4: SM-2 ease_factor floor — cards can become un-learnable

**What goes wrong:** The SM-2 algorithm decrements `ease_factor` on "Hard" (grade 3) and "Again" (grade 1) responses. If a student grades a card "Again" repeatedly, `ease_factor` can drop to or below the minimum (typically 1.3). Below 1.3, the interval calculation produces irrational intervals (e.g., negative or sub-day values). An unclamped implementation can produce `due_at` timestamps in the past or `NULL`.

**Prevention:**
- Clamp `ease_factor` to a minimum of `1.3` after every update.
- Clamp `interval` to a minimum of `1` (day) before computing `due_at`.
- Include a unit test for the "grade 1 ten times in a row" case.

**Warning signs:** Cards appear in the due queue immediately after being reviewed as "Good". `due_at` is in the past for cards that should be scheduled days out.

**Phase:** Phase 6 (SRS scheduler implementation).

---

### Pitfall M-5: Seed script mastery variance — weak_spots quiz only works if variance is real

**What goes wrong:** The `weak_spots` quiz targets the bottom-quartile mastery concepts. If the seed script sets all `mastery_score` values uniformly (e.g., all 0.5), there is no quartile variance and `weak_spots` returns a random sample, not a meaningful weak-spot set. The demo's killer feature — "one-click quiz on your weakest concepts" — looks random and unconvincing.

**Prevention:**
- Seed mastery scores with genuine variance: ~25% of concepts at 0.2–0.4 (weak), ~50% at 0.45–0.65 (medium), ~25% at 0.7–0.9 (strong).
- Ensure the "held-out" PDF adds concepts with initial mastery 0.5 (newly ingested, unreviewed) so the live drop during demo makes the weak spots quiz update visibly.
- Name the weak-spot concepts something memorable for the demo ("Kernel Trick", "Vanishing Gradient") not something generic.

**Warning signs:** `POST /quiz?scope=weak_spots` returns different concepts each call with no pattern. Demo evaluator cannot distinguish weak-spot targeting from random selection.

**Phase:** Phase 10 (seed script / demo prep).

---

## Minor Pitfalls

### Pitfall m-1: trafilatura returns empty string on JavaScript-heavy pages

**What goes wrong:** `trafilatura.extract()` is excellent for article pages but returns `None` or an empty string for React/Next.js/SPA pages that render content client-side. The URL ingestion path falls back to raw HTML in that case, which is largely unusable for extraction.

**Prevention:** After `trafilatura` extract, check if the result is longer than 200 characters. If not, fall back to `BeautifulSoup` on the raw HTML with `get_text(separator=' ')`. Log a warning.

**Phase:** Phase 2 (URL parsing).

---

### Pitfall m-2: macOS 14+ Accessibility permissions for global event monitors

**What goes wrong:** On macOS 14 (Sonoma) and 15 (Sequoia), `NSEvent.addGlobalMonitorForEvents` for keyboard events (`.keyDown`) requires the app to be granted Accessibility permission in System Settings → Privacy & Security → Accessibility. Without it, the monitor silently registers but never fires. There is no runtime error; events are simply not delivered.

**Prevention:**
- Add `NSAppleEventsUsageDescription` to `Info.plist` if using AppleScript, or prompt for Accessibility access at first launch.
- For demo: add a setup step to the README: "Open System Settings → Accessibility → add NotchDrop to the allowed list."
- Use `AXIsProcessTrustedWithOptions` to check access at startup and show an alert if not granted.

**Warning signs:** Global `⌘V` monitor registered without error but `handleClipboard` is never called when user pastes.

**Phase:** Phase 1; README step in Phase 10.

---

### Pitfall m-3: CORS missing for Swift URLSession (no Origin header)

**What goes wrong:** The spec notes CORS must allow "missing-Origin (for Swift URLSession)." The standard `fastapi.middleware.cors.CORSMiddleware` with `allow_origins=["http://localhost:3000"]` does NOT allow requests with no `Origin` header. Swift's `URLSession` does not send an `Origin` header. The result is a 400 or a preflight failure on POST /ingest from the notch app — all drops silently fail.

**Prevention:**
- Configure `allow_origins=["*"]` for local development OR handle the missing-Origin case by adding middleware that sets `Access-Control-Allow-Origin: *` when the `Origin` header is absent.
- Simpler: `allow_origins=["*"]` in dev is fine since this is single-user local demo. Note it in the README.

**Warning signs:** Swift notch app shows "Sent" in the status pill but no source row appears in the DB. Server logs show 400 or CORS errors on POST /ingest.

**Phase:** Phase 2 (API setup).

---

### Pitfall m-4: 5-second polling causes stale graph during slow extraction

**What goes wrong:** The frontend polls `GET /courses/{id}/graph` every 5 seconds. During extraction of a large PDF (20+ pages), concept nodes appear in small batches over 30–90 seconds. The dagre layout re-runs on every poll that returns new nodes, causing the entire graph to re-layout and nodes to jump to new positions. If the user has panned/zoomed, the viewport resets on every layout recalculation.

**Prevention:**
- Only re-run dagre layout when the node count changes, not on every poll. Cache the previous node set; if node IDs are the same, skip layout.
- Do not reset `fitView` on subsequent layout runs after the initial render; only call `fitView` on the first layout or when the user clicks "Re-center."

**Warning signs:** Graph nodes jump positions every 5 seconds while a PDF is processing. User interaction is interrupted.

**Phase:** Phase 5 (frontend graph + polling logic).

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|----------------|------------|
| Phase 1: NotchDrop fork | UTI ordering (C-1); NSEvent global monitor scope (C-2); Safari pasteboard types (C-3) | Log all UTI types on every drop; test with both Safari and Chrome before declaring done |
| Phase 2: Backend pipeline scaffolding | BackgroundTask shutdown loss (C-4); session leak (C-5); Alembic Vector column (C-6); CORS missing Origin (m-3); force-reingest flag (M-3) | Write reconciliation on startup; test migration on clean DB; add force=true |
| Phase 3: Embeddings | Dimension mismatch (C-8); ivfflat on small dataset (C-7) | Single EMBEDDING_MODEL constant; skip ivfflat index until 500+ rows |
| Phase 4: Concept extraction + resolution | Claude JSON failures (C-9); hallucinated concepts (C-9); cache invalidation on prompt change (M-2); resolution threshold tuning (M-1) | Use tool_use schema; manual DB inspection; TRUNCATE cache after prompt changes |
| Phase 5: React Flow graph | dagre v12 API (C-10); node re-render performance (C-11); viewport jumping on poll (m-4) | Copy official v12 dagre example; nodeTypes outside component; skip layout when nodes unchanged |
| Phase 6: SRS scheduler | SM-2 ease_factor floor (M-4) | Clamp ease_factor >= 1.3; unit test pathological case |
| Phase 10: Demo prep | Seed mastery variance (M-5); trafilatura on SPAs (m-1); accessibility permissions (m-2) | Explicit mastery distribution in seed; README setup checklist |

---

## Demo-Day Risk Register

The following are the highest-probability failures during a live hackathon demo, ranked by likelihood:

1. **Live drop fails silently** (C-1, C-3) — Probability: HIGH. Mitigation: test drop with the exact browser/file type you will use in the demo 30 minutes before. Have a fallback: the web uploader on the Library page.
2. **Pipeline stuck in `processing`** (C-4) — Probability: MEDIUM-HIGH. Mitigation: restart reconciliation on startup; never use `kill -9` uvicorn; have the seed data pre-loaded so the live drop is additive.
3. **Graph nodes all at origin** (C-10) — Probability: MEDIUM. Mitigation: copy official v12 dagre example; smoke-test graph render before demo.
4. **Weak spots quiz looks random** (M-5) — Probability: MEDIUM without attention. Mitigation: verify mastery variance in seed data the night before.
5. **⌘V paste fails in browser** (C-2) — Probability: MEDIUM. Mitigation: in the demo script, click the notch zone before pasting. Frame it as intentional.
6. **Connection pool exhaustion** (C-5) — Probability: LOW if session scoping is correct, HIGH if not. Mitigation: test seeding + several drops before demo.

---

## Sources

- FastAPI BackgroundTasks official docs — confirmed: no persistence, no shutdown guarantee (HIGH confidence)
- Apple Developer Documentation — NSEvent global monitors, Accessibility entitlements (HIGH confidence from training, macOS 14/15 behavior)
- NSItemProvider / UTI ordering — documented Apple developer forums behavior, confirmed in NotchDrop upstream issues (HIGH confidence)
- pgvector README — ivfflat lists recommendation, dimension constraints (HIGH confidence from training through Aug 2025)
- React Flow v12 / xyflow migration guide — nodeTypes stability, dagre integration pattern change (HIGH confidence from training)
- Anthropic tool_use documentation — structured output reliability, JSON truncation on long context (MEDIUM confidence; recommend verifying against current Claude API docs before Phase 4)
- SM-2 algorithm specification — ease_factor minimum 1.3 is canonical (HIGH confidence)
- trafilatura docs — SPA limitation documented (HIGH confidence)
