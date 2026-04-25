# Cortex

## What This Is

Cortex is a second brain for students, built around three tightly integrated surfaces: **Cortex Drop** (a fork of Lakr233/NotchDrop) lets students passively ingest PDFs, URLs, images, and text by dragging into the macOS notch; **Cortex API** (FastAPI) parses that content, builds a course-rooted knowledge graph with concept extraction and edge inference, and auto-generates spaced-repetition flashcards and quizzes; **Cortex Web** (Next.js) visualizes the graph and drives active recall sessions. Single-user, hackathon scope.

## Core Value

A student drops content into the notch → Cortex automatically builds a course-rooted knowledge graph and generates ready-to-study flashcards — zero manual effort between "I have this PDF" and "I'm studying these concepts."

## Requirements

### Validated

(None yet — ship to validate)

### Active

**Ingestion (Cortex Drop)**
- [ ] Drag a PDF from Finder into the notch → source row created with `source_type=pdf`
- [ ] Drag a browser tab URL into the notch → source row created with `source_type=url`
- [ ] Drag an image from a browser into the notch → source row created with `source_type=image`
- [ ] ⌘V an image (clipboard) while notch is active → `source_type=image`
- [ ] ⌘V a text snippet while notch is active → `source_type=text`
- [ ] ⌘V a URL string while notch is active → `source_type=url`
- [ ] Notch displays Cortex status pill (Sending / Sent / Error) per drop
- [ ] CortexSettings panel: toggle Cortex on/off, set backend URL, set active course ID
- [ ] When Cortex is disabled, notch falls back to original NotchDrop file-shelf behavior

**Backend pipeline**
- [ ] POST /ingest accepts multipart (pdf/image) and JSON (url/text); returns `{source_id, status: "pending"}` immediately
- [ ] Background pipeline: parse → chunk → embed → extract concepts → resolve → infer edges → generate flashcards → update mastery
- [ ] content_hash deduplication prevents re-processing identical content
- [ ] extraction_cache (keyed on chunk hash + model version) prevents redundant LLM calls
- [ ] Pipeline records `status=error` + stack trace summary on failure; does not crash the server
- [ ] CORS allows `http://localhost:3000` and missing-Origin (for Swift URLSession)

**Parsing**
- [ ] PDF: pymupdf page-by-page text, `{page_num}` in chunk metadata
- [ ] Image: Claude vision OCR → markdown (text + LaTeX equations + diagram descriptions)
- [ ] URL: httpx fetch + trafilatura clean text; title from `<title>` tag
- [ ] Text: normalize whitespace; use first 60 chars or supplied title

**Knowledge graph**
- [ ] Concepts extracted per chunk: 0–6, Title Case, singular, canonical
- [ ] Concept resolution scoped to course: cosine similarity ≥ 0.92 → merge; 0.80–0.92 → LLM tiebreaker; < 0.80 → new concept
- [ ] Concepts from different courses are NEVER merged, even if identical titles
- [ ] Edges: `course → concept` (contains), `concept ↔ concept` (co-occurrence, prerequisite, related)
- [ ] `concepts.depth` computed via BFS from course root through contains + prerequisite edges
- [ ] GET /courses/{id}/graph returns course root node + all concept nodes + all edges

**Struggle detection & mastery**
- [ ] Five struggle signals detected: repeated_confusion, retention_gap, gotcha_dense, practice_failure, neglected
- [ ] `mastery_score` initialized 0.5, updated by flashcard grades and quiz attempts, clamped [0, 1]

**Flashcards & SRS**
- [ ] Flashcards auto-generated when a new concept is created (3–6 cards, mixed types: definition/application/gotcha/compare)
- [ ] SM-2 scheduler: grades 1/3/4/5 (Again/Hard/Good/Easy) update interval, ease_factor, repetitions, due_at
- [ ] GET /flashcards/due returns cards due for review; POST /flashcards/{id}/review accepts grade and returns next card

**Quiz**
- [ ] POST /quiz accepts scope: `course` | `weak_spots` | `concept_ids` + num_questions
- [ ] `weak_spots` = bottom-quartile mastery concepts in the course
- [ ] Quiz questions: MCQ + short_answer + application, weighted toward high-gotcha concepts
- [ ] Free-response graded by Claude: returns `{correct, feedback}`
- [ ] Quiz attempts feed mastery (correct +0.05, incorrect -0.08)
- [ ] GET /quiz/{id}/results returns score breakdown + concepts to review

**Frontend**
- [ ] Dashboard: courses list, "Create Course" button, global stats (cards due today, weakest concepts)
- [ ] Course graph: React Flow, course node center, concept nodes sized by source_count, colored by mastery (red/yellow/green), struggle flags as pulsing dot, dagre layout by depth
- [ ] Node detail panel: mastery bar, summary, gotchas (amber), key points, examples, student questions, source citations, flashcard summary with "Review" button, "Generate quiz" button
- [ ] Study page: one card at a time, show front → Show Answer → grade buttons, progress bar
- [ ] Quiz page: linear walkthrough, MCQ radio or textarea, results with per-question explanations
- [ ] Library page: sources list with status badges, course assignment, web uploader (fallback)
- [ ] Graph polls every 5s for new concepts while a source is processing

**Demo readiness**
- [ ] `scripts/seed_demo.py`: loads CS 229 course with 3 PDFs + 1 chat log + 1 problem set; generates concepts/edges/flashcards/quiz attempts with mastery variance; holds out 1 PDF + 1 URL for live drops
- [ ] Full README with setup + demo script
- [ ] All 11 acceptance test steps from spec §8 pass end-to-end

### Out of Scope

- User auth / accounts — single-user hackathon demo, user_id=1 hardcoded
- Multi-user or collaboration — out of scope by design
- Real-time UI updates via WebSocket/SSE — polling every 5s is sufficient
- Mobile responsive — desktop-only (notch app is macOS-only anyway)
- Code-signing or notarizing the notch app — run from Xcode, ad-hoc signed for demo
- Production deployment — local demo only
- Streaming LLM responses — background tasks return complete results
- Rich source viewer — source text accessible via citations in the node detail panel only
- Upstream NotchDrop features beyond the Cortex module — preserve original behavior, minimize diff

## Context

- **NotchDrop fork**: Lakr233/NotchDrop is MIT-licensed; the fork adds a `Cortex/` subfolder inside `NotchDrop/NotchDrop/` to minimize the diff against upstream. All four new Swift files live there; only the tray drop handler in the existing codebase gets a surgical edit.
- **Exact Swift filenames**: discovered by Claude Code on clone (search for `@main`, `onDrop`, `NSItemProvider`, settings view) — not guessed. Spec §1.1 walk-through is the protocol.
- **License compliance**: original NotchDrop `LICENSE` file preserved; `NOTICE.md` added crediting Lakr Aream.
- **LLM discipline**: every Claude call wrapped in retry (max 2), 30s timeout, structured logging. `extraction_cache` table prevents re-spend on re-runs.
- **Concurrency caps**: 5 parallel chunk extractions, 3 parallel flashcard generations, `asyncio.sleep(0.2)` between batches if rate-limited.
- **Resolver thresholds**: 0.92 / 0.80 are starting points — spec instructs manual DB inspection after Phase 4 and tuning.
- **Pasteboard quirks**: CortexIngest.handleClipboard priority order — image → URL → string — handles common cases. Log pasteboard types if a paste produces nothing.
- **Build order** (from spec §10): Phase 0 → Phase 2 → Phase 1 → Phase 3 → Phase 4 → Phase 5 → Phase 7 → Phase 8 → Phase 9 → Phase 6 → Phase 10.

## Constraints

- **Tech stack**: Fully locked — Swift/SwiftUI (notch), Next.js 14 App Router + TypeScript + Tailwind + shadcn/ui + React Flow (web), FastAPI + uvicorn (API), Postgres 16 + pgvector (DB), Anthropic `claude-sonnet-4-5` (extraction/OCR/generation), OpenAI `text-embedding-3-small` 1536-dim (embeddings), pymupdf (PDF), httpx + trafilatura (URL), SQLAlchemy 2.0 + Alembic (ORM/migrations)
- **Timeline**: Hackathon — demo must land; phases have hour estimates (Phase 1 is 5–6 hr, the centerpiece)
- **Single-user**: user_id=1 hardcoded throughout; no auth middleware, no multi-tenancy logic
- **Dev infra**: Docker Compose for Postgres + pgvector only; everything else runs locally
- **Scope discipline**: Ask before any architectural deviations from the spec

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fork NotchDrop instead of building custom notch app | MIT-licensed, battle-tested macOS notch UI; saves ~2 days of low-level AppKit work | — Pending |
| Cortex/ subfolder isolation in fork | Minimizes diff, easier to read at demo, easier to merge upstream changes | — Pending |
| Course-scoped concept resolution (never cross-course) | Prevents "Gradient Descent" in ML from polluting a Biology course graph | — Pending |
| SM-2 for SRS scheduling | Proven algorithm, simple implementation; no need for custom scheduler at hackathon scale | — Pending |
| extraction_cache keyed on (chunk_hash, model_version) | Prevents re-spending LLM tokens on every code change during iteration | — Pending |
| `weak_spots` quiz scope = bottom-quartile mastery | Makes "one-click weak spots quiz" the killer demo button; mastery variance from seed data makes it immediately compelling | — Pending |
| content_hash deduplication on ingest | Prevents duplicate concept nodes from repeated drops of same PDF | — Pending |
| Poll every 5s for graph updates (no WebSocket) | Sufficient for demo; eliminates real-time infrastructure complexity | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-25 after initialization*
