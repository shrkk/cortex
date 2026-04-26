# Phase 4: Flashcards, Struggle & Quiz - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the two no-op pipeline stubs (`_stage_flashcards_stub`, `_stage_signals_stub`) in `backend/app/pipeline/pipeline.py` with real LLM-based implementations, and add `POST /quiz`, `GET /quiz/{id}/results`, and `POST /quiz/{id}/answer` API endpoints. The schema (`flashcards`, `quizzes`, `concepts.struggle_signals`) is already in the DB from migration 0001 — no new Alembic migrations needed for base tables.

**No SRS.** Flashcard nodes have no `due_at`, `ease_factor`, or `repetitions` columns. Flip-only.
**No mastery scoring.** `struggle_signals` feed quiz generation only, not a 0–1 score.

</domain>

<decisions>
## Implementation Decisions

### Flashcard Generation

- **D-01:** One LLM call per concept, returns all 3–6 cards as a JSON array using `tool_use`. Follow the Phase 3 `AsyncAnthropic` + `tool_use` pattern from `backend/app/pipeline/extractor.py`.
- **D-02:** Gotcha cards are generated one per entry in `Concept.gotchas`. They are always included regardless of total card count (they can push the total above 6). The 3–6 cap applies to definition + application + compare cards only.
- **D-03:** Always generate a minimum of 2 cards (definition + application) per concept, even if no gotchas or related_concepts exist.
- **D-04:** Idempotency: skip flashcard generation for concepts that already have flashcards (`len(concept.flashcards) > 0`). Prevents duplicate cards on re-runs.
- **D-05:** Max 3 parallel LLM calls (use `asyncio.Semaphore(3)`). Add `asyncio.sleep(0.2)` between batches if rate-limited.
- **D-06:** `_stage_flashcards_stub` operates on all concepts associated with the current `source_id` via `ConceptSource` (session-per-stage pattern; open own `AsyncSessionLocal`).

### Struggle Signal Detection

- **D-07:** `_stage_signals_stub` recomputes signals only for concepts touched by the current source run (concepts whose `concept_sources` include the current `source_id`). Not course-wide.
- **D-08:** STRUGGLE-01 (repeated_confusion): requires embedding comparison of `student_questions` from `chat_log` ConceptSources. If a concept has no chat_log ConceptSources, skip STRUGGLE-01 silently; still evaluate STRUGGLE-03 (gotcha_dense) and STRUGGLE-04 (practice_failure).
- **D-09:** STRUGGLE-03 (gotcha_dense): detect text patterns `"actually,"`, `"common mistake,"`, `"be careful,"`, `"a subtle point"` in chunks linked to the concept — purely deterministic, no LLM call needed.
- **D-10:** STRUGGLE-04 (practice_failure): check `source.source_metadata` for a `problem_incorrect: true` flag on sources linked to the concept.
- **D-11:** Struggle signals written to `concepts.struggle_signals` as a JSONB dict: `{"repeated_confusion": bool, "retention_gap": bool, "gotcha_dense": bool, "practice_failure": bool}`. Only include keys for signals that were actually evaluated (skip keys for unevaluated signals, don't set to false).

### Quiz Answer Storage

- **D-12:** No new migration needed. Extend `quizzes.questions` JSON in-place: each question object gets `answered: bool`, `answer: str | null`, and `grading: {correct: bool, feedback: str} | null` fields added when `POST /quiz/{id}/answer` is called.
- **D-13:** `POST /quiz/{id}/answer` returns `{grading, next_question}`. When the last question is answered, `next_question` is `null` and the response also includes `{is_complete: true, score, correct_count, total, concepts_to_review}` inline — client does not need a separate call to `GET /quiz/{id}/results`.
- **D-14:** `GET /quiz/{id}/results` returns the same shape as the terminal answer response for clients that want to re-fetch results after the quiz completes.

### Quiz Question Generation

- **D-15:** One LLM call for the full quiz. Provide all selected concept summaries + gotchas as context; tool_use returns a `questions` array of the requested `num_questions`. Single call — no per-concept calls.
- **D-16:** Question type distribution — weighted thirds: `round(num_questions * 0.4)` MCQ, `round(num_questions * 0.3)` short_answer, remainder application. Example: 7 questions → 3 MCQ, 2 short_answer, 2 application.
- **D-17:** MCQ question JSON schema:
  ```json
  {
    "type": "mcq",
    "question": "...",
    "options": ["A...", "B...", "C...", "D..."],
    "correct_index": 2,
    "concept_id": 42,
    "answered": false,
    "answer": null,
    "grading": null
  }
  ```
  Short-answer/application omit `options` and `correct_index`; include `reference_answer` (for Claude grading context only — never exposed to frontend).
- **D-18:** Concept selection priority for quiz: (1) concepts with active struggle signals first, (2) concepts with most source coverage (`len(concept_sources)`), (3) random sample to fill `num_questions`. Scope: always scoped to `course_id`.
- **D-19:** Free-response grading via `AsyncAnthropic` with `tool_use` (same client pattern as extractor). Returns `{correct: bool, feedback: "1–2 sentences"}`. The `reference_answer` is injected into the system prompt — not shown to the user.

### Claude's Discretion
- Exact flashcard prompts (front/back wording style, tone)
- Exact quiz question prompts
- How to detect STRUGGLE-02 (retention_gap) session boundaries — use source `created_at` timestamps to identify sources ≥ 24h apart; two such sources with overlapping `concept_sources` for the same concept = retention_gap

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Pipeline (session-per-stage, AsyncAnthropic, tool_use)
- `backend/app/pipeline/pipeline.py` — Stage orchestration; `_stage_flashcards_stub` and `_stage_signals_stub` are the stubs to replace; session-per-stage pattern
- `backend/app/pipeline/extractor.py` — tool_use pattern with `AsyncAnthropic`, `asyncio.Semaphore`, retry-on-parse-failure — replicate this exact pattern for flashcard and quiz LLM calls
- `backend/app/pipeline/resolver.py` — concept lookup by course_id pattern; how to query concepts touched by a source

### Data Models
- `backend/app/models/models.py` — `Flashcard` (concept_id, front, back, card_type), `Quiz` (course_id, questions: JSON), `Concept` (struggle_signals: JSON, gotchas: JSON, related_concepts: JSON)
- `backend/alembic/versions/0001_initial.py` — Confirms flashcards/quizzes tables created in initial migration; no new migrations needed for base tables

### API Patterns
- `backend/app/api/ingest.py` — BackgroundTasks pattern + FastAPI route structure to replicate for /quiz endpoints
- `backend/app/api/courses.py` — Course-scoped query pattern, `user_id=1` hardcoded

### Requirements (Phase 4)
- `.planning/REQUIREMENTS.md` §Flashcards (FLASH-01–06), §Struggle Detection (STRUGGLE-01–06), §Quiz (QUIZ-01–06)
- `.planning/ROADMAP.md` §Phase 4 — Goal, success criteria, stack notes

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AsyncAnthropic` client in `extractor.py` — identical pattern for flashcard and quiz LLM calls; use `tool_use` with `tool_choice={"type": "tool", "name": "..."}` and `additionalProperties: false`
- `asyncio.Semaphore(N)` concurrency limiter in `extractor.py` — use `Semaphore(3)` for flashcard generation
- `AsyncSessionLocal` session-per-stage pattern — each new pipeline stage opens its own session context

### Established Patterns
- All pipeline stages follow: `async with AsyncSessionLocal() as session:` → query → transform → commit → close
- `tool_use` stop_reason check: `if message.stop_reason == "tool_use"` then `tool_block = next(b for b in message.content if b.type == "tool_use")`
- Test mocking: `AsyncMock` + `MagicMock` for Anthropic responses (see `test_pipeline.py`)

### Integration Points
- `_stage_flashcards_stub` (pipeline stage 7): replace stub with call to `backend/app/pipeline/flashcards.py`
- `_stage_signals_stub` (pipeline stage 8): replace stub with call to `backend/app/pipeline/signals.py`
- New module files follow Phase 3 pattern: `extractor.py`, `resolver.py`, `edges.py` — create `flashcards.py` and `signals.py` in `backend/app/pipeline/`
- New API router: `backend/app/api/quiz.py` — registered in `backend/app/main.py` same as `ingest.py` and `courses.py`

</code_context>

<specifics>
## Specific Ideas

- STRUGGLE-03 detection is purely deterministic (string search in chunk text) — no LLM call needed. Check chunks linked to concept via `ConceptSource → Source → Chunk` join.
- Quiz `reference_answer` field is stored in the question JSON but must never be returned in any GET endpoint response — strip it in the response serializer.
- When `POST /quiz` receives `num_questions` larger than the number of available concepts in the course, cap silently at the concept count × 2 (concepts can appear in multiple question types).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 4-flashcards-struggle-quiz*
*Context gathered: 2026-04-25*
