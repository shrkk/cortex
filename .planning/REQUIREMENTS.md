# Requirements: Cortex

**Defined:** 2026-04-25
**Core Value:** A student drops content into the notch → Cortex automatically builds a course-rooted knowledge graph and generates ready-to-study flashcards — zero manual effort between "I have this PDF" and "I'm studying these concepts."

## v1 Requirements

### Infrastructure

- [ ] **INFRA-01**: Docker Compose runs Postgres 16 + pgvector; `docker compose up` produces a healthy DB
- [ ] **INFRA-02**: GET /health returns 200 with `{"status": "ok"}`
- [ ] **INFRA-03**: Alembic migration creates all tables, indexes, and extensions in one run against a fresh DB
- [ ] **INFRA-04**: Seed script (`scripts/seed_demo.py`) loads user id=1 with pre-existing courses so the notch's course-matching flow has data to work with from first launch
- [ ] **INFRA-05**: `.env.example` documents all required environment variables

### Ingestion — Cortex Drop (NotchDrop fork)

- [ ] **ING-01**: User drags a PDF from Finder into the notch → source row created with `source_type=pdf`
- [ ] **ING-02**: User drags a browser tab URL into the notch → source row created with `source_type=url`
- [ ] **ING-03**: User drags an image from a browser into the notch → source row created with `source_type=image`
- [ ] **ING-04**: User copies an image (⌘C) and presses ⌘V while the notch is active → `source_type=image`
- [ ] **ING-05**: User copies a text snippet (⌘C) and presses ⌘V while the notch is active → `source_type=text`
- [ ] **ING-06**: User copies a URL string (⌘C) and presses ⌘V while the notch is active → `source_type=url`
- [ ] **ING-07**: Notch displays a status pill: "Sending to Cortex…" during upload → "Sent to [Course Name]" on success → error message on failure; pill fades after 2s (success) or 4s (error)
- [ ] **ING-08**: CortexSettings panel allows toggling Cortex on/off and setting backend URL; no static course ID field
- [ ] **ING-09**: When Cortex is disabled, notch falls back to original NotchDrop file-shelf behavior without modification
- [ ] **ING-10**: License: original NotchDrop LICENSE file preserved; NOTICE.md added crediting Lakr Aream
- [ ] **ING-11**: No courses exist → before uploading, notch shows the course label tab with a text input "Name this course" + confirm button; course is created then upload proceeds automatically
- [ ] **ING-12**: Courses exist → Swift client fires GET /courses/match?hint=[filename or content preview] pre-flight; confidence ≥ 0.65 → auto-assign silently and upload; status pill shows "Sent to [Course Name]"
- [ ] **ING-13**: Courses exist but no confident match (confidence < 0.65 or null) → notch shows the course label tab with a list of existing course names + "New course…" option; user taps a course or types a new name before upload proceeds
- [ ] **ING-14**: Course label tab is a compact SwiftUI component (`CortexCourseTab.swift`) that slides inline into the expanded notch — not a separate window or popover
- [ ] **ING-15**: Last-selected course is remembered as a session default; the next drop within the same session pre-selects it in the label tab (user can still change it)

### Parsing

- [ ] **PARSE-01**: PDF sources parsed page-by-page with pymupdf; chunk metadata includes `page_num`
- [ ] **PARSE-02**: Image sources sent to Claude vision for OCR → raw markdown (text verbatim, equations as LaTeX, diagrams described); title = "Image: " + first 60 chars
- [ ] **PARSE-03**: URL sources fetched with httpx (10s timeout, follow redirects) and extracted with trafilatura; title from `<title>` tag; URL stored in `source_uri`
- [ ] **PARSE-04**: arXiv `arxiv.org/abs/` URLs automatically rewritten to `arxiv.org/pdf/` and routed to the PDF parser
- [ ] **PARSE-05**: Text sources normalize whitespace; title = supplied title or first 60 chars

### Pipeline

- [ ] **PIPE-01**: POST /ingest accepts multipart/form-data (file + course_id + kind) and application/json ({course_id, kind, url} or {course_id, kind, title, text}); returns `{source_id, status: "pending"}` immediately
- [ ] **PIPE-02**: Background pipeline executes: parse → chunk → embed → extract → resolve → edges → flashcards → struggle signals; writes `status=done` on completion
- [ ] **PIPE-03**: `content_hash` (sha256 of raw_text) prevents re-processing identical content; duplicate detected → `metadata.duplicate_of` set, pipeline exits early
- [ ] **PIPE-04**: `extraction_cache` table keyed on `(chunk_hash, model_version)` is checked before every LLM extraction call
- [ ] **PIPE-05**: Pipeline catches all exceptions; writes `status=error` and stack trace summary to `sources.error`
- [ ] **PIPE-06**: On server startup, any sources with `status=processing` are reset to `status=pending` (guards against silent task loss on restart)
- [ ] **PIPE-07**: CORS allows `http://localhost:3000` and requests with no `Origin` header (Swift URLSession sends none)

### Concept Extraction

- [ ] **EXTRACT-01**: Each chunk yields 0–6 concepts; concepts are specific study units (not generic skills or abbreviations-only)
- [ ] **EXTRACT-02**: Extracted concept fields: title (Title Case, singular, canonical), definition, key_points, gotchas, examples, related_concepts
- [ ] **EXTRACT-03**: Student questions extracted verbatim only for `chat_log` source types
- [ ] **EXTRACT-04**: LLM called via tool_use with strict JSON Schema (`additionalProperties: false`) to prevent malformed output; retries once on parse failure
- [ ] **EXTRACT-05**: Max 5 chunks processed in parallel; extraction_cache checked before every call

### Concept Resolution

- [ ] **RESOLVE-01**: Resolution is strictly course-scoped — concepts from different courses are never merged
- [ ] **RESOLVE-02**: Cosine similarity ≥ 0.92 → merge (append concept_sources row with new key_points/gotchas/examples/questions)
- [ ] **RESOLVE-03**: Cosine similarity 0.80–0.91 → LLM tiebreaker: `{"same": bool, "reason": "string"}`; merge if same=true
- [ ] **RESOLVE-04**: Cosine similarity < 0.80 → create new concept node
- [ ] **RESOLVE-05**: Two PDFs covering "Gradient Descent" in the same course produce ONE concept node; same topic in different courses produces two separate nodes

### Edges

- [ ] **EDGE-01**: Course → concept `contains` edge created automatically when a new concept is added
- [ ] **EDGE-02**: Co-occurrence edges created between every pair of concepts extracted from the same chunk; weight incremented on repeated co-occurrence
- [ ] **EDGE-03**: Prerequisite edges inferred by LLM per course (batched, max 50 concepts/call, max 30 edges/output)
- [ ] **EDGE-04**: `concepts.depth` recomputed via BFS from course root through `contains` + `prerequisite` edges after edge inference

### Flashcards

- [ ] **FLASH-01**: Flashcards auto-generated when a new concept is created (3–6 cards per concept)
- [ ] **FLASH-02**: Card types: `definition` (what the concept is), `application` (applying it to a scenario), `gotcha` (one card per distinct gotcha, front sets up the trap, back explains mistake + correction), `compare` (distinguishing from a related concept, only if obvious)
- [ ] **FLASH-03**: Flashcard nodes appear on the knowledge graph connected to their parent concept node
- [ ] **FLASH-04**: User can navigate to a concept's flashcards by clicking the concept node and selecting "Flashcards"
- [ ] **FLASH-05**: User can flip a flashcard (front → back) without any grading or scheduling
- [ ] **FLASH-06**: No SRS scheduling — cards have no due dates, ease factors, or repetition counts

### Struggle Detection

- [ ] **STRUGGLE-01**: Repeated confusion detected: concept's aggregated questions contain ≥ 3 with embedding similarity > 0.75
- [ ] **STRUGGLE-02**: Retention gap detected: questions about a concept appear in chat sources across ≥ 2 sessions ≥ 24h apart
- [ ] **STRUGGLE-03**: Gotcha-dense detected: any chunk linked to concept contains "actually,", "common mistake,", "be careful,", "a subtle point"
- [ ] **STRUGGLE-04**: Practice failure detected: source metadata flags a problem wrong and the chunk was linked to this concept
- [ ] **STRUGGLE-05**: Struggle signals stored in `concepts.struggle_signals` JSONB; used exclusively to inform quiz generation (not for mastery scoring)
- [ ] **STRUGGLE-06**: Concepts with active struggle signals display a pulsing indicator on their graph node

### Quiz

- [ ] **QUIZ-01**: Quiz is a standalone node type on the knowledge graph, connected directly to the course root node
- [ ] **QUIZ-02**: POST /quiz generates a quiz; scope priority: (1) concepts with struggle signals, (2) concepts with most source coverage; accepts `{course_id, num_questions}`
- [ ] **QUIZ-03**: Quiz questions mix types: MCQ, short_answer, application — weighted toward concepts with more gotchas
- [ ] **QUIZ-04**: Free-response answers graded by Claude: returns `{correct: bool, feedback: "1–2 sentences"}`
- [ ] **QUIZ-05**: GET /quiz/{id}/results returns score breakdown and list of concepts to review
- [ ] **QUIZ-06**: POST /quiz/{id}/answer accepts `{question_id, answer}`, grades it, returns next question or final results

### Graph API

- [ ] **GRAPH-01**: GET /courses returns all courses for user
- [ ] **GRAPH-02**: POST /courses creates a new course; returns course with id
- [ ] **GRAPH-03**: GET /courses/{id}/graph returns course root node, all concept nodes, all flashcard nodes, all quiz nodes, and all edges
- [ ] **GRAPH-04**: GET /concepts/{id} returns concept detail: summary, key_points, gotchas, examples, student questions, source citations, flashcard count, struggle signals
- [ ] **GRAPH-05**: Graph node types: `course` (root), `concept`, `flashcard`, `quiz`
- [ ] **GRAPH-06**: Graph polls for updates every 5s on the frontend while any source is `status=pending` or `status=processing`
- [ ] **GRAPH-07**: GET /courses/match?hint=[text] embeds the hint and returns `{course_id, title, confidence}` for the best-matching course, or `null` if best confidence < 0.65; hint is filename, URL title, or first 200 chars of content

### Frontend

- [ ] **UI-01**: Dashboard (`/`) shows courses list, "Create Course" button, global stats (total concepts, active struggle signals)
- [ ] **UI-02**: Course graph (`/courses/[id]`) renders React Flow graph: course node at center, concept nodes sized by source_count, colored by struggle (red = has signals, neutral = none), dagre layout by depth, flashcard and quiz nodes visible
- [ ] **UI-03**: Concept nodes with active struggle signals show a pulsing red indicator
- [ ] **UI-04**: Edge types rendered distinctly: `contains` (thick neutral), `prerequisite` (solid arrow), `co_occurrence` (dashed), `related` (dotted)
- [ ] **UI-05**: Clicking a concept node opens a detail panel: summary, gotchas (amber highlight), key_points, examples, student questions, source citations with chunk text, flashcard count with "View Flashcards" button, "Generate Quiz" button
- [ ] **UI-06**: "View Flashcards" opens flip-card study mode: one card, front shown, "Show Answer" reveals back, "Next" advances to next card — no grading
- [ ] **UI-07**: Quiz node on graph is clickable; clicking opens the quiz walkthrough
- [ ] **UI-08**: Quiz page (`/quiz/[id]`) is a linear walkthrough: MCQ radio or textarea, submit answer, see feedback + correct answer, advance; final screen shows score and concepts to review
- [ ] **UI-09**: Library (`/library`) shows all sources with status badges (`pending`, `processing`, `done`, `error`), course assignment dropdown, and a web file uploader (labeled "fallback uploader — prefer dropping into the notch")
- [ ] **UI-10**: Empty states: "Drop something into the notch to get started" on empty graph; "No flashcards yet" on empty flashcard view
- [ ] **UI-11**: Graph re-fetches automatically every 5s while any source is processing; stops polling when all sources are `done` or `error`

### Demo Readiness

- [ ] **DEMO-01**: `scripts/seed_demo.py` loads CS 229 course with 3 PDFs (backprop, regularization, probability primer), 1 chat log of a confused student, 1 problem set with two wrong answers
- [ ] **DEMO-02**: Seed produces ~20 concept nodes with varied struggle signals: ≥ 3 with active signals, ≥ 3 without
- [ ] **DEMO-03**: Seed holds out 1 PDF and 1 URL for live drops during the demo
- [ ] **DEMO-04**: Full README with setup steps (including Accessibility permission for ⌘V) and demo script
- [ ] **DEMO-05**: All 11 acceptance test steps from spec §8 pass end-to-end on a fresh DB

## v2 Requirements

### SRS / Scheduled Review

- **SRS-01**: SM-2 spaced repetition scheduling for flashcard review (due dates, ease factor, intervals)
- **SRS-02**: "Cards due today" dashboard widget
- **SRS-03**: Flashcard grading (Again / Hard / Good / Easy) with interval updates

### Mastery Tracking

- **MASTERY-01**: Concept mastery score (0–1) updated by quiz attempts and flashcard grades
- **MASTERY-02**: Graph nodes colored by mastery (red < 0.4, yellow 0.4–0.7, green > 0.7)
- **MASTERY-03**: "Weak spots" quiz scope based on bottom-quartile mastery

### Collaboration & Auth

- **AUTH-01**: User accounts with email/password
- **AUTH-02**: Multiple users with isolated course graphs

## Out of Scope

| Feature | Reason |
|---------|--------|
| User authentication / accounts | Single-user hackathon; user_id=1 hardcoded |
| Multi-user or collaboration | Out of scope by design |
| Real-time UI via WebSocket/SSE | 5s polling is sufficient for demo |
| Mobile responsive design | Desktop-only; notch app is macOS-only |
| Code-signing / notarizing the notch app | Run from Xcode, ad-hoc signed for demo |
| Production deployment | Local demo only |
| Streaming LLM responses | Background tasks return complete results |
| Rich source viewer | Chunk text accessible via citations in detail panel only |
| Mastery scoring | Removed by design — struggle signals feed quiz, not a score |
| SRS scheduling (due dates, ease factor) | Removed by design — flashcards are always-accessible graph nodes |
| Flashcard grading | Removed by design — flip-and-review only, no scoring |

## Traceability

*Populated during roadmap creation.*

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01–05 | Phase 1 | Pending |
| ING-01–15 | Phase 2 | Pending |
| PARSE-01–05 | Phase 3 | Pending |
| PIPE-01–07 | Phase 3 | Pending |
| EXTRACT-01–05 | Phase 4 | Pending |
| RESOLVE-01–05 | Phase 4 | Pending |
| EDGE-01–04 | Phase 5 | Pending |
| FLASH-01–06 | Phase 6 | Pending |
| STRUGGLE-01–06 | Phase 6 | Pending |
| QUIZ-01–06 | Phase 6 | Pending |
| GRAPH-01–07 | Phase 7 | Pending |
| UI-01–11 | Phase 8 | Pending |
| DEMO-01–05 | Phase 9 | Pending |

**Coverage:**
- v1 requirements: 71 total
- Mapped to phases: 71
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-25*
*Last updated: 2026-04-25 after initial definition*
