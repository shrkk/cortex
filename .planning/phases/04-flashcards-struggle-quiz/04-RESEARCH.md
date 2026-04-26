# Phase 4: Flashcards, Struggle & Quiz — Research

**Researched:** 2026-04-25
**Domain:** LLM-based flashcard generation, deterministic struggle signal detection, quiz generation and grading, FastAPI JSON-mutation endpoints
**Confidence:** HIGH (all patterns verified from existing codebase; no new packages required)

---

## Summary

Phase 4 replaces two pipeline stubs (`_stage_flashcards_stub`, `_stage_signals_stub`) in `backend/app/pipeline/pipeline.py` and adds three new API endpoints (`POST /quiz`, `GET /quiz/{id}/results`, `POST /quiz/{id}/answer`). The entire schema is already in place from migration `0001_initial.py` — `flashcards` and `quizzes` tables with all required columns exist, and `concepts.struggle_signals` is already a `JSON` column. No new Alembic migrations are needed.

All patterns needed for Phase 4 are already established in the codebase. Flashcard generation follows the exact same `AsyncAnthropic` + `tool_use` + `asyncio.Semaphore(3)` pattern that Phase 3 defines for `extractor.py`. Struggle signal detection is split between deterministic string-search (STRUGGLE-03, STRUGGLE-04) and embedding-based aggregation (STRUGGLE-01, STRUGGLE-02); no LLM call is required for signals. Quiz generation follows the same single-LLM-call `tool_use` pattern. Quiz answer grading (STRUGGLE-04 free-response) uses the same `AsyncAnthropic` client. The three new API endpoints follow the `ingest.py` + `courses.py` router pattern with `AsyncSessionLocal` direct sessions (not `Depends(get_session)` for background-like operations).

The most critical design subtleties are: (1) `reference_answer` must be stored in the questions JSON but stripped before ANY GET response, (2) `struggle_signals` JSONB must only include keys for signals that were actually evaluated — do not set unevaluated keys to false, (3) STRUGGLE-01 requires cosine comparison of embedded student questions, which requires the OpenAI client inside `signals.py`, and (4) the quiz questions array is mutated in-place by `POST /quiz/{id}/answer` — SQLAlchemy will not auto-detect JSON column mutations without explicit `flag_modified`.

**Primary recommendation:** Create `backend/app/pipeline/flashcards.py` and `backend/app/pipeline/signals.py` (pipeline stage modules) and `backend/app/api/quiz.py` (router), then wire them into `pipeline.py` and `router.py` following the established patterns exactly.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** One LLM call per concept for flashcards, returns all 3–6 cards as a JSON array using `tool_use`. Follow the Phase 3 `AsyncAnthropic` + `tool_use` pattern from `backend/app/pipeline/extractor.py`.

**D-02:** Gotcha cards are generated one per entry in `Concept.gotchas`. They are always included regardless of total card count (they can push the total above 6). The 3–6 cap applies to definition + application + compare cards only.

**D-03:** Always generate a minimum of 2 cards (definition + application) per concept, even if no gotchas or related_concepts exist.

**D-04:** Idempotency: skip flashcard generation for concepts that already have flashcards (`len(concept.flashcards) > 0`). Prevents duplicate cards on re-runs.

**D-05:** Max 3 parallel LLM calls (use `asyncio.Semaphore(3)`). Add `asyncio.sleep(0.2)` between batches if rate-limited.

**D-06:** `_stage_flashcards_stub` operates on all concepts associated with the current `source_id` via `ConceptSource` (session-per-stage pattern; open own `AsyncSessionLocal`).

**D-07:** `_stage_signals_stub` recomputes signals only for concepts touched by the current source run (concepts whose `concept_sources` include the current `source_id`). Not course-wide.

**D-08:** STRUGGLE-01 (repeated_confusion): requires embedding comparison of `student_questions` from `chat_log` ConceptSources. If a concept has no chat_log ConceptSources, skip STRUGGLE-01 silently; still evaluate STRUGGLE-03 (gotcha_dense) and STRUGGLE-04 (practice_failure).

**D-09:** STRUGGLE-03 (gotcha_dense): detect text patterns `"actually,"`, `"common mistake,"`, `"be careful,"`, `"a subtle point"` in chunks linked to the concept — purely deterministic, no LLM call needed.

**D-10:** STRUGGLE-04 (practice_failure): check `source.source_metadata` for a `problem_incorrect: true` flag on sources linked to the concept.

**D-11:** Struggle signals written to `concepts.struggle_signals` as a JSONB dict: `{"repeated_confusion": bool, "retention_gap": bool, "gotcha_dense": bool, "practice_failure": bool}`. Only include keys for signals that were actually evaluated (skip keys for unevaluated signals, don't set to false).

**D-12:** No new migration needed. Extend `quizzes.questions` JSON in-place: each question object gets `answered: bool`, `answer: str | null`, and `grading: {correct: bool, feedback: str} | null` fields added when `POST /quiz/{id}/answer` is called.

**D-13:** `POST /quiz/{id}/answer` returns `{grading, next_question}`. When the last question is answered, `next_question` is `null` and the response also includes `{is_complete: true, score, correct_count, total, concepts_to_review}` inline — client does not need a separate call to `GET /quiz/{id}/results`.

**D-14:** `GET /quiz/{id}/results` returns the same shape as the terminal answer response for clients that want to re-fetch results after the quiz completes.

**D-15:** One LLM call for the full quiz. Provide all selected concept summaries + gotchas as context; tool_use returns a `questions` array of the requested `num_questions`. Single call — no per-concept calls.

**D-16:** Question type distribution — weighted thirds: `round(num_questions * 0.4)` MCQ, `round(num_questions * 0.3)` short_answer, remainder application.

**D-17:** MCQ question JSON schema includes `type`, `question`, `options`, `correct_index`, `concept_id`, `answered`, `answer`, `grading`. Short-answer/application omit `options` and `correct_index`; include `reference_answer` (never exposed to frontend).

**D-18:** Concept selection priority for quiz: (1) concepts with active struggle signals first, (2) concepts with most source coverage (`len(concept_sources)`), (3) random sample to fill `num_questions`. Scope: always scoped to `course_id`.

**D-19:** Free-response grading via `AsyncAnthropic` with `tool_use` (same client pattern as extractor). Returns `{correct: bool, feedback: "1–2 sentences"}`. The `reference_answer` is injected into the system prompt — not shown to the user.

**No SRS.** Flashcard nodes have no `due_at`, `ease_factor`, or `repetitions` columns. Flip-only.
**No mastery scoring.** `struggle_signals` feed quiz generation only, not a 0–1 score.

### Claude's Discretion
- Exact flashcard prompts (front/back wording style, tone)
- Exact quiz question prompts
- How to detect STRUGGLE-02 (retention_gap) session boundaries — use source `created_at` timestamps to identify sources ≥ 24h apart; two such sources with overlapping `concept_sources` for the same concept = retention_gap

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FLASH-01 | Flashcards auto-generated when a new concept is created (3–6 cards per concept) | `flashcards.py` pipeline stage; `Semaphore(3)`; tool_use per concept |
| FLASH-02 | Card types: definition, application, gotcha (one per distinct gotcha), compare (if obvious) | Tool schema encodes all card types; D-02/D-03 define card count logic |
| FLASH-03 | Flashcard nodes appear on the knowledge graph connected to their parent concept node | Already modeled: `Flashcard.concept_id` FK; graph API Phase 5 exposes the relationship |
| FLASH-04 | User can navigate to a concept's flashcards via "Flashcards" button | Frontend (Phase 6); backend query is `SELECT flashcards WHERE concept_id = :id` |
| FLASH-05 | User can flip a flashcard (front → back) without grading or scheduling | Frontend-only toggle; no DB write on flip (confirmed by schema: no SRS columns) |
| FLASH-06 | No SRS scheduling — cards have no due dates, ease factors, or repetition counts | Confirmed: `flashcards` table has only `id`, `concept_id`, `front`, `back`, `card_type`, `created_at` |
| STRUGGLE-01 | Repeated confusion: ≥ 3 student questions with embedding similarity > 0.75 | Requires OpenAI embeddings; pairwise cosine; only for chat_log ConceptSources (D-08) |
| STRUGGLE-02 | Retention gap: questions about a concept appear in chat sources across ≥ 2 sessions ≥ 24h apart | Compare `source.created_at` across chat_log ConceptSources per concept (Claude's Discretion) |
| STRUGGLE-03 | Gotcha-dense: any chunk linked to concept contains trigger phrases | Deterministic string search on chunk.text via ConceptSource → Source → Chunk join |
| STRUGGLE-04 | Practice failure: source metadata flags a problem wrong and chunk linked to concept | Check `source.source_metadata["problem_incorrect"] == True` via ConceptSource → Source join |
| STRUGGLE-05 | Signals stored in `concepts.struggle_signals` JSONB; used only for quiz generation | Already a JSON column in DB; update via `sa.update` + `flag_modified` |
| STRUGGLE-06 | Concepts with active struggle signals display a pulsing indicator | Frontend (Phase 6); backend exposes `struggle_signals` in concept detail |
| QUIZ-01 | Quiz is a standalone node type on the knowledge graph, connected to the course root | `Quiz` model has `course_id` FK; no concept-level FK; graph API (Phase 5) synthesizes edge |
| QUIZ-02 | POST /quiz generates quiz; scope priority: struggle signals > source coverage; accepts `{course_id, num_questions}` | D-18 concept selection algorithm; one LLM call (D-15) |
| QUIZ-03 | Quiz questions mix types: MCQ, short_answer, application — weighted toward gotcha-heavy concepts | D-16 distribution formula; D-17 JSON schema |
| QUIZ-04 | Free-response answers graded by Claude: returns `{correct: bool, feedback: "1–2 sentences"}` | D-19 grading tool_use pattern; `reference_answer` in system prompt |
| QUIZ-05 | GET /quiz/{id}/results returns score breakdown and concepts to review | D-14: same shape as terminal answer response; strip `reference_answer` from output |
| QUIZ-06 | POST /quiz/{id}/answer accepts `{question_id, answer}`, grades it, returns next question or final results | D-12/D-13: mutate questions JSON in-place; `flag_modified` required |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Flashcard LLM generation | API / Backend (pipeline stage 7) | — | Background task called from `run_pipeline`; no HTTP surface |
| Flashcard persistence | Database / Storage | API Backend | `flashcards` table; `concept_id` FK |
| Struggle signal detection | API / Backend (pipeline stage 8) | Database | Reads chunks, sources, embeddings; writes to `concepts.struggle_signals` |
| Quiz concept selection | API / Backend (POST /quiz handler) | Database | Queries `concepts` filtered by `course_id` and `struggle_signals` |
| Quiz LLM generation | API / Backend (POST /quiz handler) | — | Single `AsyncAnthropic` tool_use call inline |
| Quiz persistence | Database / Storage | API Backend | `quizzes.questions` JSON column |
| Answer grading (MCQ) | API / Backend (POST /quiz/{id}/answer) | — | Deterministic: compare `answer` to `options[correct_index]` |
| Answer grading (free-response) | API / Backend → Anthropic | — | `AsyncAnthropic` grading call; `reference_answer` in system prompt |
| Reference answer exposure | API / Backend (response serializer) | — | Strip `reference_answer` before returning ANY response |
| Quiz results computation | API / Backend (GET /quiz/{id}/results) | Database | Reads `quizzes.questions` JSON; computes score in Python |
| Struggle graph indicator | Frontend / Client | — | Phase 6 reads `struggle_signals` from concept detail endpoint |

---

## Standard Stack

### Core (all already in requirements.txt — no new installs)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `anthropic` | 0.97.0 | `AsyncAnthropic` for flashcard + quiz LLM calls, grading | Already pinned; established pattern in `parsers.py` and Phase 3 extractor |
| `openai` | 2.32.0 | `text-embedding-3-small` for STRUGGLE-01 question embeddings | Already pinned; identical to chunk embedding pattern in `pipeline.py` |
| `sqlalchemy` | 2.0.49 | Async ORM queries, `flag_modified` for JSON mutation | Already pinned; session-per-stage pattern established |
| `fastapi` | 0.136.1 | `APIRouter` for `/quiz` endpoints | Already pinned; pattern established in `ingest.py` and `courses.py` |

[VERIFIED: backend/requirements.txt]

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `asyncio.Semaphore` | stdlib | Limit parallel flashcard LLM calls to 3 | FLASH-01 concurrency limit (D-05) |
| `sqlalchemy.orm.attributes.flag_modified` | via SQLAlchemy | Signal JSON column mutation to SQLAlchemy ORM | QUIZ-06: mutating `quizzes.questions` in-place |
| `numpy` or math | stdlib `math` | Cosine similarity for STRUGGLE-01 | Compute pairwise cosine of embedded question vectors |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `flag_modified` for JSON mutation | Replace full list via `quiz.questions = [...]` reassignment | Reassignment always works but requires loading + rebuilding the full list; `flag_modified` is cleaner signal for mutation tracking |
| Pairwise cosine in Python | Store embeddings in pgvector and use SQL | Question embeddings are transient (not stored); Python pairwise is simpler for small sets (< 50 questions per concept) |

**Installation:** No new packages needed. [VERIFIED: backend/requirements.txt — all packages already declared]

---

## Architecture Patterns

### System Architecture Diagram

```
pipeline.run_pipeline(source_id)
  │
  ├─ [stages 1-6: parse, chunk, embed, extract, resolve, edges — Phase 2+3]
  │
  ├─ _stage_flashcards(source_id)       ← replaces _stage_flashcards_stub
  │    │
  │    ├─ SELECT concepts via ConceptSource WHERE source_id = :sid
  │    ├─ filter: skip concepts with len(flashcards) > 0 (D-04 idempotency)
  │    ├─ asyncio.Semaphore(3) — max 3 parallel LLM calls
  │    │    └─ for each concept:
  │    │         ├─ build context: title, definition, gotchas, related_concepts
  │    │         ├─ AsyncAnthropic tool_use → [{front, back, card_type}, ...]
  │    │         └─ INSERT Flashcard rows for concept
  │    └─ commit
  │
  ├─ _stage_signals(source_id)          ← replaces _stage_signals_stub
  │    │
  │    ├─ SELECT concepts via ConceptSource WHERE source_id = :sid
  │    └─ for each concept:
  │         ├─ [STRUGGLE-03] string search in chunk.text via ConceptSource→Source→Chunk
  │         ├─ [STRUGGLE-04] check source.source_metadata["problem_incorrect"]
  │         ├─ [STRUGGLE-02] compare source.created_at across chat_log sources ≥24h apart
  │         ├─ [STRUGGLE-01] embed student_questions → pairwise cosine; ≥3 pairs >0.75
  │         ├─ build signals dict (only evaluated keys included)
  │         └─ UPDATE concepts.struggle_signals WHERE id = :cid
  │
  └─ _stage_set_done(source_id)


POST /quiz (courses/{course_id}, num_questions)
  │
  ├─ SELECT concepts WHERE course_id = :cid
  ├─ sort by: (1) has struggle_signals, (2) len(concept_sources), (3) random
  ├─ cap num_questions at len(concepts) * 2
  ├─ AsyncAnthropic single tool_use call → questions array
  │    └─ questions include reference_answer (for grading only — never returned)
  ├─ INSERT Quiz(course_id, questions=[...])
  └─ return {quiz_id, questions (stripped of reference_answer)}


POST /quiz/{id}/answer (question_id, answer)
  │
  ├─ load Quiz by id
  ├─ find question by question_id
  ├─ grade:
  │    ├─ MCQ: compare answer to options[correct_index]
  │    └─ short_answer/application: AsyncAnthropic grading call (D-19)
  │         └─ reference_answer injected into system prompt
  ├─ mutate question dict: answered=true, answer=..., grading={correct, feedback}
  ├─ flag_modified(quiz, "questions")  ← CRITICAL: SQLAlchemy JSON mutation signal
  ├─ commit
  ├─ if last question answered:
  │    └─ return {grading, next_question: null, is_complete: true, score, correct_count, total, concepts_to_review}
  └─ else:
       └─ return {grading, next_question: {stripped question object}}


GET /quiz/{id}/results
  │
  ├─ load Quiz by id
  ├─ compute score from questions[].grading.correct
  ├─ collect concepts_to_review from questions where grading.correct == false
  └─ return same shape as terminal answer response (stripped of reference_answer)
```

### Recommended Project Structure
```
backend/app/
├── pipeline/
│   ├── pipeline.py       # Modified: replace stubs with real calls to flashcards.py + signals.py
│   ├── parsers.py        # Unchanged
│   ├── extractor.py      # Phase 3 (will exist by Phase 4 execution)
│   ├── resolver.py       # Phase 3 (will exist by Phase 4 execution)
│   ├── edges.py          # Phase 3 (will exist by Phase 4 execution)
│   ├── flashcards.py     # NEW: _stage_flashcards(source_id)
│   └── signals.py        # NEW: _stage_signals(source_id)
├── api/
│   ├── router.py         # Modified: add quiz router registration
│   ├── ingest.py         # Unchanged
│   ├── courses.py        # Unchanged
│   └── quiz.py           # NEW: POST /quiz, GET /quiz/{id}/results, POST /quiz/{id}/answer
├── schemas/
│   └── quiz.py           # NEW: QuizCreate, QuizResponse, AnswerRequest, AnswerResponse
└── models/
    └── models.py         # Unchanged (all models already present)
```

### Pattern 1: Flashcard LLM Tool Schema

```python
# Source: Phase 3 extractor pattern (03-PATTERNS.md) adapted for flashcard cards
# tool_use with additionalProperties: false — matches EXTRACT-04 convention

FLASHCARD_TOOL = {
    "name": "generate_flashcards",
    "description": (
        "Generate study flashcards for this concept. "
        "Always include at minimum a definition card and an application card. "
        "Include one gotcha card per distinct gotcha in the concept. "
        "Include a compare card only if the concept has obvious related concepts to compare against. "
        "The 3–6 total cap applies only to definition + application + compare cards; "
        "gotcha cards are additional and unlimited."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["cards"],
        "properties": {
            "cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["front", "back", "card_type"],
                    "properties": {
                        "front": {
                            "type": "string",
                            "description": "Question or prompt side of the card"
                        },
                        "back": {
                            "type": "string",
                            "description": "Answer or explanation side of the card"
                        },
                        "card_type": {
                            "type": "string",
                            "enum": ["definition", "application", "gotcha", "compare"]
                        }
                    }
                }
            }
        }
    }
}

# Call pattern — same as extractor.py tool_use (03-PATTERNS.md)
message = await client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2048,
    tools=[FLASHCARD_TOOL],
    tool_choice={"type": "tool", "name": "generate_flashcards"},
    messages=[{
        "role": "user",
        "content": (
            f"Concept: {concept.title}\n"
            f"Definition: {concept.definition}\n"
            f"Gotchas: {concept.gotchas}\n"
            f"Related concepts: {concept.related_concepts}\n\n"
            f"Generate flashcards for this concept."
        )
    }]
)
if message.stop_reason == "tool_use":
    tool_block = next(b for b in message.content if b.type == "tool_use")
    cards = tool_block.input.get("cards", [])  # already a Python list — no json.loads
```

[VERIFIED: 03-PATTERNS.md — tool_use call pattern, stop_reason check, tool_block.input dict access]
[VERIFIED: backend/app/pipeline/parsers.py — AsyncAnthropic client instantiation pattern]

### Pattern 2: Semaphore + Idempotency for Flashcard Generation

```python
# Source: 03-RESEARCH.md Pattern 3 (asyncio.Semaphore), adapted to Semaphore(3)
import asyncio

async def _stage_flashcards(source_id: int) -> None:
    if not settings.anthropic_api_key:
        return  # skip if no key — matches _stage_embed guard pattern

    import anthropic
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    sem = asyncio.Semaphore(3)

    async with AsyncSessionLocal() as session:
        # Get all concepts touched by this source (D-06)
        result = await session.execute(
            sa.select(Concept)
            .join(ConceptSource, ConceptSource.concept_id == Concept.id)
            .where(ConceptSource.source_id == source_id)
            .options(sa.orm.selectinload(Concept.flashcards))  # load flashcards for idempotency check
        )
        concepts = result.scalars().all()

    async def generate_for_concept(concept):
        async with sem:
            if len(concept.flashcards) > 0:
                return  # D-04 idempotency: already has flashcards
            cards = await _call_flashcard_llm(concept, client)
            async with AsyncSessionLocal() as session:
                for card in cards:
                    session.add(Flashcard(
                        concept_id=concept.id,
                        front=card["front"],
                        back=card["back"],
                        card_type=card["card_type"],
                    ))
                await session.commit()

    await asyncio.gather(*[generate_for_concept(c) for c in concepts])
```

[VERIFIED: backend/app/models/models.py — Flashcard fields: id, concept_id, front, back, card_type, created_at]
[VERIFIED: backend/app/models/models.py — Concept.flashcards relationship]

### Pattern 3: Struggle Signal Detection (Deterministic)

```python
# STRUGGLE-03: gotcha_dense — string search in chunks linked to concept (D-09)
# Path: ConceptSource → Source → Chunk (via source.chunks)

GOTCHA_PHRASES = ["actually,", "common mistake,", "be careful,", "a subtle point"]

async with AsyncSessionLocal() as session:
    # Load concept_sources with their sources and chunks
    result = await session.execute(
        sa.select(ConceptSource)
        .join(Source, Source.id == ConceptSource.source_id)
        .join(Chunk, Chunk.source_id == Source.id)
        .where(ConceptSource.concept_id == concept.id)
        .add_columns(Chunk.text)
    )
    rows = result.all()

gotcha_dense = any(
    phrase in chunk_text.lower()
    for _, chunk_text in rows
    for phrase in GOTCHA_PHRASES
)

# STRUGGLE-04: practice_failure — check source metadata (D-10)
# Source.source_metadata is mapped to "metadata" column (Python attribute name = source_metadata)
practice_failure = any(
    (cs.source.source_metadata or {}).get("problem_incorrect") is True
    for cs in concept.concept_sources
)
```

[VERIFIED: backend/app/models/models.py — Source.source_metadata mapped to "metadata" column (line 59)]
[VERIFIED: backend/app/models/models.py — ConceptSource.source relationship]
[VERIFIED: backend/app/models/models.py — Chunk.source_id FK]

### Pattern 4: STRUGGLE-02 Retention Gap Detection (Claude's Discretion)

```python
# Retention gap: same concept cited in ≥2 chat_log sources ≥24h apart
from datetime import timezone

async with AsyncSessionLocal() as session:
    result = await session.execute(
        sa.select(Source.created_at)
        .join(ConceptSource, ConceptSource.source_id == Source.id)
        .where(
            ConceptSource.concept_id == concept.id,
            Source.source_type == "chat_log",
        )
        .order_by(Source.created_at)
    )
    chat_times = [row.created_at for row in result.all()]

retention_gap = False
if len(chat_times) >= 2:
    # Check if any two sources are ≥ 24h apart
    for i in range(len(chat_times)):
        for j in range(i + 1, len(chat_times)):
            delta = chat_times[j] - chat_times[i]
            if delta.total_seconds() >= 86400:  # 24h
                retention_gap = True
                break
```

[VERIFIED: backend/app/models/models.py — Source.source_type, Source.created_at, ConceptSource joins]
[ASSUMED] — session boundary interpretation uses source.created_at comparison; 24h threshold from CONTEXT.md Claude's Discretion

### Pattern 5: STRUGGLE-01 Repeated Confusion (Embedding Comparison)

```python
# STRUGGLE-01: ≥3 student_question pairs with cosine similarity > 0.75
# student_questions are stored per ConceptSource for chat_log sources

import math

def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)

# Collect all student questions from chat_log concept sources
all_questions: list[str] = []
async with AsyncSessionLocal() as session:
    result = await session.execute(
        sa.select(ConceptSource)
        .join(Source, Source.id == ConceptSource.source_id)
        .where(
            ConceptSource.concept_id == concept.id,
            Source.source_type == "chat_log",
            ConceptSource.student_questions.isnot(None),
        )
    )
    for cs in result.scalars().all():
        all_questions.extend(cs.student_questions or [])

if len(all_questions) < 3:
    # Cannot have ≥3 similar pairs — skip STRUGGLE-01 (D-08)
    pass
else:
    # Embed all questions in one batch call
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    embed_resp = await openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=all_questions,
    )
    vectors = [e.embedding for e in embed_resp.data]

    # Count pairs with similarity > 0.75
    similar_pairs = 0
    for i in range(len(vectors)):
        for j in range(i + 1, len(vectors)):
            if _cosine_sim(vectors[i], vectors[j]) > 0.75:
                similar_pairs += 1

    repeated_confusion = similar_pairs >= 3
```

[VERIFIED: backend/app/models/models.py — ConceptSource.student_questions is JSON (list)]
[VERIFIED: backend/app/pipeline/pipeline.py — OpenAI batch embed pattern (lines 181–186)]
[ASSUMED] — pairwise cosine in Python (not pgvector) because question embeddings are transient/not stored

### Pattern 6: Writing Struggle Signals with flag_modified

```python
# CRITICAL: SQLAlchemy does not auto-detect JSON column mutations
# Must use flag_modified to mark the column dirty before commit

from sqlalchemy.orm.attributes import flag_modified

async with AsyncSessionLocal() as session:
    result = await session.execute(
        sa.select(Concept).where(Concept.id == concept_id)
    )
    concept = result.scalar_one()

    # Build signals dict — only include evaluated keys (D-11)
    signals: dict = {}
    if gotcha_dense is not None:
        signals["gotcha_dense"] = gotcha_dense
    if practice_failure is not None:
        signals["practice_failure"] = practice_failure
    if retention_gap is not None:
        signals["retention_gap"] = retention_gap
    if repeated_confusion is not None:
        signals["repeated_confusion"] = repeated_confusion

    concept.struggle_signals = signals
    flag_modified(concept, "struggle_signals")  # REQUIRED for JSON mutation
    await session.commit()
```

[VERIFIED: backend/app/models/models.py — Concept.struggle_signals is JSON column (line 103)]
[ASSUMED] — flag_modified requirement for SQLAlchemy JSON columns; standard SQLAlchemy 2.0 pattern

### Pattern 7: Quiz Generation Tool Schema

```python
# D-17: MCQ and free-response schemas in a single tool call

QUIZ_TOOL = {
    "name": "generate_quiz",
    "description": (
        "Generate quiz questions for a set of course concepts. "
        "Mix MCQ, short_answer, and application types per the requested distribution. "
        "Include reference_answer for short_answer and application questions "
        "(used for grading only — never shown to the student)."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["questions"],
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["type", "question", "concept_id"],
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["mcq", "short_answer", "application"]
                        },
                        "question": {"type": "string"},
                        "concept_id": {
                            "type": "integer",
                            "description": "ID of the concept this question tests"
                        },
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "MCQ only: 4 answer options"
                        },
                        "correct_index": {
                            "type": "integer",
                            "description": "MCQ only: 0-based index of correct option"
                        },
                        "reference_answer": {
                            "type": "string",
                            "description": "short_answer/application only: used for grading, never shown to student"
                        }
                    }
                }
            }
        }
    }
}
```

[VERIFIED: CONTEXT.md D-17 — exact JSON schema specification]

### Pattern 8: Quiz API Endpoint (POST /quiz)

```python
# Source: backend/app/api/ingest.py — direct AsyncSessionLocal usage pattern (not Depends)
# Source: backend/app/api/courses.py — APIRouter + response_model pattern

from fastapi import APIRouter, HTTPException
from sqlalchemy import insert

from app.core.database import AsyncSessionLocal
from app.models.models import Concept, ConceptSource, Quiz
from app.schemas.quiz import QuizCreate, QuizResponse

router = APIRouter()

@router.post("", response_model=QuizResponse, status_code=201)
async def create_quiz(body: QuizCreate):
    """Generate a quiz scoped to a course.

    POST /quiz body: {course_id: int, num_questions: int}
    """
    async with AsyncSessionLocal() as session:
        # Concept selection (D-18)
        result = await session.execute(
            sa.select(Concept)
            .where(Concept.course_id == body.course_id)
            .options(sa.orm.selectinload(Concept.concept_sources))
        )
        concepts = result.scalars().all()

    if not concepts:
        raise HTTPException(404, "No concepts found for this course")

    # Sort: struggle signals first, then source coverage, then random
    import random
    def _concept_priority(c):
        has_signals = bool(c.struggle_signals)
        source_count = len(c.concept_sources)
        return (not has_signals, -source_count, random.random())

    concepts_sorted = sorted(concepts, key=_concept_priority)

    # Cap num_questions (D-15 special case)
    max_questions = len(concepts) * 2
    num_q = min(body.num_questions, max_questions)

    # Single LLM call for all questions
    questions = await _generate_quiz_questions(concepts_sorted, num_q)

    # Annotate questions with answered/answer/grading initial state
    for q in questions:
        q["answered"] = False
        q["answer"] = None
        q["grading"] = None

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            insert(Quiz).values(
                course_id=body.course_id,
                questions=questions,
            ).returning(Quiz.id)
        )
        quiz_id = result.scalar_one()
        await session.commit()

    # Strip reference_answer before returning
    return QuizResponse(
        id=quiz_id,
        course_id=body.course_id,
        questions=_strip_reference_answers(questions),
    )
```

[VERIFIED: backend/app/api/ingest.py — insert().returning() pattern, AsyncSessionLocal direct usage]
[VERIFIED: backend/app/models/models.py — Quiz.course_id, Quiz.questions]

### Pattern 9: Answer Grading and JSON Mutation (POST /quiz/{id}/answer)

```python
# D-12: mutate questions JSON in-place; D-13: return inline results on last question
# CRITICAL: flag_modified required (same as struggle_signals pattern)

from sqlalchemy.orm.attributes import flag_modified

@router.post("/{quiz_id}/answer")
async def answer_question(quiz_id: int, body: AnswerRequest):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Quiz).where(Quiz.id == quiz_id)
        )
        quiz = result.scalar_one_or_none()
        if not quiz:
            raise HTTPException(404, "Quiz not found")

        questions = quiz.questions or []
        target_q = next(
            (q for q in questions if q.get("question_id") == body.question_id),
            None
        )
        if not target_q:
            raise HTTPException(404, "Question not found")

        # Grade
        if target_q["type"] == "mcq":
            option_text = target_q["options"][target_q["correct_index"]]
            correct = body.answer.strip().lower() == option_text.strip().lower()
            grading = {"correct": correct, "feedback": "Correct!" if correct else f"The correct answer is: {option_text}"}
        else:
            # Free-response: Claude grading (D-19)
            grading = await _grade_free_response(
                question=target_q["question"],
                student_answer=body.answer,
                reference_answer=target_q.get("reference_answer", ""),
            )

        # Mutate in-place
        target_q["answered"] = True
        target_q["answer"] = body.answer
        target_q["grading"] = grading
        flag_modified(quiz, "questions")  # REQUIRED
        await session.commit()

        # Check if complete
        all_answered = all(q.get("answered") for q in questions)
        next_q = next((q for q in questions if not q.get("answered")), None)

        response = {"grading": grading, "next_question": _strip_ref(next_q)}
        if all_answered:
            correct_count = sum(1 for q in questions if (q.get("grading") or {}).get("correct"))
            total = len(questions)
            concepts_to_review = list({
                q["concept_id"] for q in questions
                if not (q.get("grading") or {}).get("correct")
            })
            response.update({
                "is_complete": True,
                "score": round(correct_count / total, 2) if total else 0,
                "correct_count": correct_count,
                "total": total,
                "concepts_to_review": concepts_to_review,
            })
        return response
```

[VERIFIED: CONTEXT.md D-12, D-13 — exact response shape specification]
[ASSUMED] — `flag_modified` requirement; standard SQLAlchemy 2.0 JSON mutation pattern

### Pattern 10: Router Registration

```python
# Source: backend/app/api/router.py — exact pattern to follow

# backend/app/api/router.py — add quiz router:
from app.api import health, courses, ingest, quiz

router.include_router(quiz.router, prefix="/quiz", tags=["quiz"])
```

[VERIFIED: backend/app/api/router.py — existing router.include_router pattern]

### Pattern 11: Pipeline Wiring

```python
# Source: backend/app/pipeline/pipeline.py — stubs being replaced (lines 215-222)
# Follow lazy import pattern from parsers (03-PATTERNS.md pipeline wiring section)

# In pipeline.py — replace stubs with:
async def _stage_flashcards_stub(source_id: int) -> None:
    # renamed to real implementation caller:
    from app.pipeline.flashcards import run_flashcards
    await run_flashcards(source_id)

async def _stage_signals_stub(source_id: int) -> None:
    from app.pipeline.signals import run_signals
    await run_signals(source_id)

# NOTE: The stub names in run_pipeline() stay the same in the call site;
# the stub functions themselves are replaced with real implementations.
# Alternatively rename to _stage_flashcards and _stage_signals and update run_pipeline.
```

[VERIFIED: backend/app/pipeline/pipeline.py — run_pipeline call sequence lines 37-38]

### Anti-Patterns to Avoid

- **Returning reference_answer in ANY response:** `reference_answer` stored in `quizzes.questions` JSON must be stripped in every response path — `POST /quiz`, `GET /quiz/{id}/results`, `POST /quiz/{id}/answer` (next_question). Build a `_strip_reference_answers` helper and call it in all three paths.
- **Setting struggle_signals keys to False for unevaluated signals:** D-11 explicitly says omit keys for unevaluated signals. If a concept has no chat_log ConceptSources, do NOT set `"repeated_confusion": false`.
- **Mutating quizzes.questions without flag_modified:** SQLAlchemy will not detect in-place dict mutations in JSON columns. The session will commit with no changes. Always call `flag_modified(quiz, "questions")` before commit.
- **Course-wide signal recomputation:** D-07 says signals recompute only for concepts touched by the current source_id run. Never scan all concepts in the course.
- **Multiple LLM calls for quiz:** D-15 mandates one call. Do not loop per concept.
- **Generating flashcards for concepts that already have them:** D-04 mandates idempotency check `len(concept.flashcards) > 0`. Load the relationship eagerly via `selectinload`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured flashcard output | Regex/string parsing | `tool_use` with `additionalProperties: false` | Claude may add commentary to free-text; tool_use guarantees schema |
| Approximate cosine nearest-neighbor for concepts | Manual scan | pgvector HNSW index (already in place) | But note: STRUGGLE-01 uses Python pairwise because question vectors are transient |
| Free-response grading logic | Rule-based text match | `AsyncAnthropic` grading call (D-19) | Too many valid phrasings; LLM is the right tool |
| JSON mutation persistence | Direct dict update only | `flag_modified(model, "field")` | SQLAlchemy JSON type does not track nested mutations automatically |

**Key insight:** The `flag_modified` requirement is the single most likely implementation bug in this phase. Every place that mutates a JSON column without reassignment needs this call.

---

## Common Pitfalls

### Pitfall 1: reference_answer Exposure
**What goes wrong:** `reference_answer` appears in the API response, revealing answers to students.
**Why it happens:** The field is stored in the `quizzes.questions` JSON list. Any response that serializes `quiz.questions` directly will include it.
**How to avoid:** Write a `_strip_reference_answers(questions: list) -> list` helper that removes `reference_answer` from every question dict. Call it in all three response paths.
**Warning signs:** `POST /quiz` response body contains `"reference_answer"` key; a student inspects the API response.

### Pitfall 2: flag_modified Not Called After JSON Mutation
**What goes wrong:** `POST /quiz/{id}/answer` appears to succeed (returns 200) but the next load of the quiz shows the question is still `answered=False`.
**Why it happens:** SQLAlchemy's JSON type tracker does not notice when you mutate a nested dict in-place. `session.commit()` sees no dirty columns and writes nothing.
**How to avoid:** After mutating any dict within `quiz.questions`, call `flag_modified(quiz, "questions")` before `await session.commit()`.
**Warning signs:** `GET /quiz/{id}/results` always returns score=0 even after answering all questions; quiz.questions shows all `answered: false` after commit.

### Pitfall 3: Struggle Signals Include False for Unevaluated Signals
**What goes wrong:** A concept with no chat_log sources gets `{"repeated_confusion": false, "retention_gap": false}` in its signals. The quiz generator treats this as evaluated (no signals), which is correct, but the frontend may display inconsistent indicator states.
**Why it happens:** Initializing the signals dict with all keys as `False` before evaluation.
**How to avoid:** D-11 explicitly says omit keys for unevaluated signals. Use an empty `signals: dict = {}` and only add keys that were actually evaluated.
**Warning signs:** Every concept has all four signal keys regardless of source type.

### Pitfall 4: Course-Wide Signal Recomputation
**What goes wrong:** Processing a single PDF triggers re-evaluation of struggle signals for all 50 concepts in the course — slow and incorrect.
**Why it happens:** Signal stage queries `Concept.course_id == course_id` instead of filtering by `ConceptSource.source_id == source_id`.
**How to avoid:** D-07: filter by `ConceptSource.source_id == source_id` to get only concepts touched in this pipeline run.
**Warning signs:** Signal stage takes minutes; same signals appear on concepts not linked to the current source.

### Pitfall 5: Flashcard Idempotency Not Checked Eagerly
**What goes wrong:** Re-running the pipeline on the same source generates duplicate flashcards because `concept.flashcards` is not loaded when checking `len(concept.flashcards) > 0`.
**Why it happens:** SQLAlchemy lazy-loads relationships by default; in async context, lazy load raises `MissingGreenlet` error or returns empty list incorrectly.
**How to avoid:** Use `selectinload(Concept.flashcards)` in the concept query within `_stage_flashcards`.
**Warning signs:** `MissingGreenlet` error on `concept.flashcards`; duplicate flashcard rows after two pipeline runs.

### Pitfall 6: num_questions Cap Not Applied
**What goes wrong:** `POST /quiz` with `num_questions=100` on a course with 5 concepts sends a 100-question prompt to Claude, which either fails or returns fewer questions than expected.
**Why it happens:** The cap `min(body.num_questions, len(concepts) * 2)` was not implemented.
**How to avoid:** Cap silently before the LLM call. No error returned — just cap.
**Warning signs:** LLM call with huge `num_questions` in prompt; quiz returns 10 questions when 100 was requested with no explanation.

### Pitfall 7: tool_use Not Forced on Single LLM Calls
**What goes wrong:** `StopIteration` when extracting the tool_block; quiz returns no questions.
**Why it happens:** `tool_choice` omitted; Claude uses `end_turn` with a text response.
**How to avoid:** Always pass `tool_choice={"type": "tool", "name": "generate_flashcards"}` (or equivalent for quiz/grading tools).
**Warning signs:** `message.stop_reason == "end_turn"` in logs; `StopIteration` from `next(b for b in message.content if b.type == "tool_use")`.

---

## Code Examples

### Complete Flashcard Stage Entry Point

```python
# Source: backend/app/pipeline/parsers.py lines 104–113 (AsyncAnthropic pattern)
# Source: backend/app/pipeline/pipeline.py lines 162–163 (API key guard)
# backend/app/pipeline/flashcards.py

from __future__ import annotations
import asyncio
import anthropic
import sqlalchemy as sa
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Concept, ConceptSource, Flashcard

async def run_flashcards(source_id: int) -> None:
    """Pipeline stage 7: generate flashcards for all concepts from this source."""
    if not settings.anthropic_api_key:
        return  # skip in dev without key

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    sem = asyncio.Semaphore(3)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Concept)
            .join(ConceptSource, ConceptSource.concept_id == Concept.id)
            .where(ConceptSource.source_id == source_id)
            .options(selectinload(Concept.flashcards))
        )
        concepts = result.scalars().unique().all()  # .unique() because join may duplicate

    async def generate_one(concept: Concept) -> None:
        async with sem:
            if concept.flashcards:  # D-04 idempotency
                return
            cards = await _call_llm(concept, client)
            async with AsyncSessionLocal() as session:
                for card in cards:
                    session.add(Flashcard(
                        concept_id=concept.id,
                        front=card["front"],
                        back=card["back"],
                        card_type=card["card_type"],
                    ))
                await session.commit()

    await asyncio.gather(*[generate_one(c) for c in concepts])
```

### Grading Tool Schema

```python
# Source: 03-PATTERNS.md tiebreaker pattern (small schema, same tool_choice forcing)
GRADE_TOOL = {
    "name": "grade_answer",
    "description": "Grade a student's free-response answer against the reference answer.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["correct", "feedback"],
        "properties": {
            "correct": {
                "type": "boolean",
                "description": "True if the student's answer is substantially correct"
            },
            "feedback": {
                "type": "string",
                "description": "1–2 sentences of constructive feedback"
            }
        }
    }
}

async def _grade_free_response(
    question: str,
    student_answer: str,
    reference_answer: str,
    client: anthropic.AsyncAnthropic,
) -> dict:
    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=f"You are grading a student response. Reference answer: {reference_answer}",
        tools=[GRADE_TOOL],
        tool_choice={"type": "tool", "name": "grade_answer"},
        messages=[{
            "role": "user",
            "content": f"Question: {question}\n\nStudent answer: {student_answer}"
        }]
    )
    tool_block = next(b for b in message.content if b.type == "tool_use")
    return tool_block.input  # {"correct": bool, "feedback": str}
```

### Reference Answer Stripping Helper

```python
def _strip_reference_answers(questions: list[dict]) -> list[dict]:
    """Remove reference_answer from all questions before returning to client.

    Must be called in: POST /quiz response, GET /quiz/{id}/results,
    POST /quiz/{id}/answer (next_question field).
    """
    return [
        {k: v for k, v in q.items() if k != "reference_answer"}
        for q in (questions or [])
    ]
```

---

## Critical Implementation Details

### SQLAlchemy JSON Mutation — flag_modified

SQLAlchemy's `JSON` column type tracks assignment to the attribute, but does NOT track mutations to nested objects (dicts/lists) that are modified in-place. The `quizzes.questions` column is mutated per-answer; without `flag_modified`, commits silently no-op.

```python
from sqlalchemy.orm.attributes import flag_modified

quiz.questions[i]["answered"] = True  # in-place mutation
flag_modified(quiz, "questions")       # tell SQLAlchemy this column is dirty
await session.commit()
```

This requirement applies equally to `concepts.struggle_signals` when updated.

[ASSUMED] — standard SQLAlchemy 2.0 behavior; verified to be correct pattern for JSON columns

### Quiz question_id Field

The D-17 schema and D-12 reference `question_id` in `POST /quiz/{id}/answer`. The quiz tool schema shown in D-17 does NOT include `question_id` as a required field — it must be added by the quiz creation code before persisting, using the 0-based index or a UUID. Using the 0-based list index is simplest:

```python
for idx, q in enumerate(questions):
    q["question_id"] = idx  # stable within the quiz; assigned at creation
    q["answered"] = False
    q["answer"] = None
    q["grading"] = None
```

[ASSUMED] — question_id assignment strategy not specified in D-17; 0-based index is simplest and deterministic

### Quiz Type Distribution Formula (D-16)

```python
# D-16: round(N*0.4) MCQ, round(N*0.3) short_answer, remainder application
# Example: N=7 → MCQ=3, short_answer=2, application=2

def _question_distribution(num_questions: int) -> tuple[int, int, int]:
    mcq = round(num_questions * 0.4)
    short = round(num_questions * 0.3)
    application = num_questions - mcq - short
    return mcq, short, max(0, application)
```

Pass the distribution to the quiz LLM prompt so Claude generates the right counts per type.

### Concept Selection Context for Quiz (D-18)

The quiz LLM call receives concept summaries as context. Since the quiz covers N concepts but the course may have many more, select the concepts first, then build the prompt:

```python
# D-18: (1) struggle signal concepts, (2) most source coverage, (3) random fill
# Select enough concepts to cover num_questions questions (≤ num_questions concepts)
selected_concepts = concepts_sorted[:num_questions]  # at most one concept per question

# Build context string for LLM prompt
context = "\n\n".join(
    f"Concept ID {c.id}: {c.title}\n"
    f"Definition: {c.definition}\n"
    f"Gotchas: {'; '.join(c.gotchas or [])}"
    for c in selected_concepts
)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Free-text JSON parsing from LLM | `tool_use` with `additionalProperties: false` | Anthropic tool_use 2023 | Guaranteed schema; no parse failures |
| SQLAlchemy JSON as full replacement | `flag_modified` for in-place mutation | SQLAlchemy 2.0 | Required for JSON column updates without reassignment |
| Mutable column types (MutableDict) | `flag_modified` | SQLAlchemy 1.4+ | Cleaner than importing MutableDict; works with any JSON type |

**Deprecated/outdated:**
- `SQLAlchemy MutableDict/MutableList`: still valid but adds complexity. `flag_modified` is simpler for this codebase.
- Free-text grading: scoring student answers by keyword matching. LLM grading (D-19) is the correct approach.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `flag_modified(model, "field")` is required when mutating JSON columns in-place in SQLAlchemy 2.0 async sessions | Pattern 6, Pattern 9 | Without it, commits silently no-op; quiz answers never persist. High risk — must verify in Wave 0 test |
| A2 | STRUGGLE-02 session boundary: two chat_log ConceptSources with `created_at` timestamps ≥24h apart → retention_gap=True | Pattern 4 | If "session" means something different (e.g., login session, not time window), detection will be wrong. Low risk — Claude's Discretion explicitly confirmed this interpretation in CONTEXT.md |
| A3 | STRUGGLE-01 question comparison uses Python pairwise cosine (not pgvector) because student_questions are not stored as embeddings | Pattern 5 | If question count grows very large (>200), Python pairwise becomes O(n²) slow. Acceptable for demo scope |
| A4 | `question_id` in POST /quiz/{id}/answer body refers to 0-based index assigned at quiz creation time (not a UUID or DB PK) | Critical Implementation Details | If frontend expects a UUID or different ID scheme, question lookup will fail. Should be confirmed in Phase 5 Graph API design |
| A5 | `result.scalars().unique().all()` is needed when joining Concept via ConceptSource (JOIN may duplicate rows for multi-source concepts) | Pattern 2 | Without `.unique()`, the same concept appears multiple times; duplicate flashcard generation attempts for a single concept |
| A6 | `selectinload(Concept.flashcards)` works correctly in async context for the idempotency check | Pattern 2 | Lazy loading in async raises MissingGreenlet; eager loading with selectinload avoids this |

---

## Open Questions

1. **quiz.questions question_id scheme**
   - What we know: D-12 says `POST /quiz/{id}/answer` accepts `{question_id, answer}`. D-17 defines the question JSON schema without a `question_id` field.
   - What's unclear: Is `question_id` a 0-based index, a UUID, or something else? The Phase 6 frontend will need to know.
   - Recommendation: Use 0-based index for simplicity. Document in Phase 5 Graph API or Phase 6 Frontend research so the UI matches.

2. **MCQ answer format for POST /quiz/{id}/answer**
   - What we know: MCQ has `options: ["A...", "B...", "C...", "D..."]` and `correct_index: 2`.
   - What's unclear: Does the student submit the full option text or the index? Grading logic depends on this.
   - Recommendation: Accept the full option text string; compare with `options[correct_index]`.strip().lower(). Simpler for frontend.

---

## Environment Availability

Phase 4 is backend-only, adding Python modules. No external tools beyond what Phase 3 already requires.

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `anthropic` SDK | Flashcard LLM, quiz LLM, grading LLM | ✓ | 0.97.0 (pinned) | Tests mock the client |
| `openai` SDK | STRUGGLE-01 question embeddings | ✓ | 2.32.0 (pinned) | Skip STRUGGLE-01 if no key |
| `ANTHROPIC_API_KEY` | LLM calls | ✓ | Set in .env | Tests mock |
| `OPENAI_API_KEY` | STRUGGLE-01 embeddings | ✓ | Set in .env | Skip signal silently |
| PostgreSQL + pgvector | All DB | ✓ | pgvector/pgvector:pg16 | — |

[VERIFIED: backend/requirements.txt — anthropic==0.97.0, openai==2.32.0 already pinned]

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 0.24.0 |
| Config file | `backend/pytest.ini` (`asyncio_mode = auto`, `testpaths = tests`) |
| Quick run command | `pytest tests/test_flashcards.py tests/test_signals.py tests/test_quiz_api.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FLASH-01 | 3–6 cards generated per concept via LLM | unit | `pytest tests/test_flashcards.py::test_flashcard_generation -x` | ❌ Wave 0 |
| FLASH-02 | All card types present; gotcha cards per gotcha entry | unit | `pytest tests/test_flashcards.py::test_card_types -x` | ❌ Wave 0 |
| FLASH-04 | Idempotency: skip concepts with existing flashcards | unit | `pytest tests/test_flashcards.py::test_idempotency -x` | ❌ Wave 0 |
| FLASH-05/06 | No SRS columns on Flashcard model | unit (structural) | `pytest tests/test_flashcards.py::test_no_srs_columns -x` | ❌ Wave 0 |
| STRUGGLE-01 | ≥3 similar question pairs → repeated_confusion=True | unit | `pytest tests/test_signals.py::test_repeated_confusion -x` | ❌ Wave 0 |
| STRUGGLE-02 | Two chat_log sources ≥24h apart → retention_gap=True | unit | `pytest tests/test_signals.py::test_retention_gap -x` | ❌ Wave 0 |
| STRUGGLE-03 | Gotcha phrase in chunk text → gotcha_dense=True | unit | `pytest tests/test_signals.py::test_gotcha_dense -x` | ❌ Wave 0 |
| STRUGGLE-04 | source_metadata.problem_incorrect=True → practice_failure=True | unit | `pytest tests/test_signals.py::test_practice_failure -x` | ❌ Wave 0 |
| STRUGGLE-05 | Signals written to concepts.struggle_signals JSONB | unit | `pytest tests/test_signals.py::test_signals_written -x` | ❌ Wave 0 |
| QUIZ-01 | Quiz has course_id FK; no concept_id FK | unit (structural) | `pytest tests/test_quiz_api.py::test_quiz_model -x` | ❌ Wave 0 |
| QUIZ-02 | POST /quiz creates quiz with correct num_questions | unit | `pytest tests/test_quiz_api.py::test_create_quiz -x` | ❌ Wave 0 |
| QUIZ-03 | Questions mix MCQ/short_answer/application per D-16 formula | unit | `pytest tests/test_quiz_api.py::test_question_distribution -x` | ❌ Wave 0 |
| QUIZ-04 | Free-response grading calls Claude, returns {correct, feedback} | unit | `pytest tests/test_quiz_api.py::test_free_response_grading -x` | ❌ Wave 0 |
| QUIZ-05 | GET /quiz/{id}/results returns score + concepts_to_review | unit | `pytest tests/test_quiz_api.py::test_quiz_results -x` | ❌ Wave 0 |
| QUIZ-06 | POST /quiz/{id}/answer mutates quiz JSON, persists correctly | unit | `pytest tests/test_quiz_api.py::test_answer_persisted -x` | ❌ Wave 0 |

### Critical Unit Tests (must verify implementation correctness)

```python
# Source: backend/tests/test_pipeline.py — mock pattern to follow

def _make_tool_response_flashcards(cards: list[dict]) -> MagicMock:
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = {"cards": cards}
    message = MagicMock()
    message.stop_reason = "tool_use"
    message.content = [tool_block]
    return message

def test_no_reference_answer_in_quiz_response():
    """reference_answer must never appear in any API response."""
    questions = [{"type": "short_answer", "question": "Q?", "reference_answer": "secret", "answered": False}]
    stripped = _strip_reference_answers(questions)
    assert "reference_answer" not in stripped[0]

def test_struggle_signals_omits_unevaluated_keys():
    """D-11: signals dict must not include False for unevaluated signals."""
    # Concept with no chat_log sources — STRUGGLE-01 and STRUGGLE-02 not evaluated
    signals = {}
    signals["gotcha_dense"] = True  # evaluated
    # repeated_confusion and retention_gap NOT added
    assert "repeated_confusion" not in signals
    assert "retention_gap" not in signals
```

### Mocking Strategy (follows established pattern from test_pipeline.py)

```python
# Mock session for JSON mutation test
mock_session = AsyncMock()
mock_session.__aenter__ = AsyncMock(return_value=mock_session)
mock_session.__aexit__ = AsyncMock(return_value=False)
mock_session.execute = AsyncMock(return_value=MagicMock())
mock_session.commit = AsyncMock()
mock_session.flush = AsyncMock()
mock_session.add = MagicMock()

# Mock flag_modified to verify it was called
with patch("sqlalchemy.orm.attributes.flag_modified") as mock_flag_modified:
    # ... call answer endpoint ...
    mock_flag_modified.assert_called_once_with(quiz, "questions")
```

### Sampling Rate
- **Per task commit:** `pytest tests/test_flashcards.py tests/test_signals.py tests/test_quiz_api.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_flashcards.py` — covers FLASH-01 through FLASH-06
- [ ] `tests/test_signals.py` — covers STRUGGLE-01 through STRUGGLE-05
- [ ] `tests/test_quiz_api.py` — covers QUIZ-01 through QUIZ-06
- [ ] `backend/app/pipeline/flashcards.py` — module stub (importable, `run_flashcards` defined as `pass`)
- [ ] `backend/app/pipeline/signals.py` — module stub (`run_signals` defined as `pass`)
- [ ] `backend/app/api/quiz.py` — router stub (routes defined but returning 501)
- [ ] `backend/app/schemas/quiz.py` — Pydantic schemas for request/response

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | user_id=1 hardcoded; no auth |
| V3 Session Management | no | no web sessions |
| V4 Access Control | no | single user |
| V5 Input Validation | yes | `additionalProperties: false` in all tool schemas; Pydantic request bodies; `num_questions` cap |
| V6 Cryptography | no | no crypto in this phase |

### Known Threat Patterns for Phase 4 Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| reference_answer exposure via API | Information Disclosure | `_strip_reference_answers()` helper called in all three response paths |
| Prompt injection via student answers in grading | Tampering | Student answer is user-supplied but Claude is the evaluator; tool_use schema rejects non-schema fields |
| Large num_questions DoS | Denial of Service | Cap at `len(concepts) * 2` before LLM call |
| Malformed question_id in POST /quiz/{id}/answer | Tampering | `next(...)` returns None → 404 response |

---

## Sources

### Primary (HIGH confidence)
- `backend/app/models/models.py` — All ORM field names confirmed: `Flashcard` (concept_id, front, back, card_type), `Quiz` (course_id, questions), `Concept` (struggle_signals JSON, gotchas JSON, related_concepts JSON), `ConceptSource` (student_questions JSON, source relationship), `Source` (source_metadata mapped to "metadata", source_type, created_at)
- `backend/alembic/versions/0001_initial.py` — Confirmed all Phase 4 tables exist: `flashcards` (id, concept_id, front, back, card_type, created_at), `quizzes` (id, course_id, questions JSON, created_at), `concepts.struggle_signals` JSON column; no additional migration needed
- `backend/app/pipeline/pipeline.py` — Confirmed stub names `_stage_flashcards_stub` and `_stage_signals_stub`; session-per-stage pattern; API key guard pattern (`if not settings.openai_api_key: return`)
- `backend/app/pipeline/parsers.py` — Confirmed `AsyncAnthropic` client instantiation pattern (lines 112–113); `model="claude-sonnet-4-6"` confirmed; tool_use is NOT used in parsers (image uses free-text), tool_use pattern comes from Phase 3 research
- `.planning/phases/03-extraction-resolution-edges/03-RESEARCH.md` — tool_use pattern with tool_choice forcing, stop_reason check, tool_block.input dict access (Patterns 1–6); asyncio.Semaphore pattern; session-per-stage established
- `.planning/phases/03-extraction-resolution-edges/03-PATTERNS.md` — Exact mock patterns for tests; patch target naming; _make_tool_response helper pattern
- `backend/app/api/ingest.py` — `insert().returning()` pattern; direct `AsyncSessionLocal` usage (not `Depends(get_session)`) for background-like operations
- `backend/app/api/courses.py` — `APIRouter` pattern, `response_model`, `user_id=1` hardcoded convention
- `backend/app/api/router.py` — `router.include_router` with prefix pattern
- `backend/requirements.txt` — anthropic==0.97.0, openai==2.32.0 confirmed; no new packages needed
- `.planning/phases/04-flashcards-struggle-quiz/04-CONTEXT.md` — All locked decisions D-01 through D-19

### Secondary (MEDIUM confidence)
- `backend/tests/test_pipeline.py` — AsyncMock/MagicMock session mock structure; `asyncio_mode = auto` pytest.ini confirmed
- `backend/app/core/database.py` — `expire_on_commit=False` confirmed; `async_sessionmaker` pattern

### Tertiary (LOW confidence)
- `flag_modified` SQLAlchemy requirement [ASSUMED] — standard 2.0 behavior for JSON columns; not tested from existing codebase (no existing JSON mutation code to reference)
- Python pairwise cosine for STRUGGLE-01 [ASSUMED] — embedding question vectors transiently rather than storing in DB
- question_id assignment as 0-based index [ASSUMED] — not specified in D-17 schema

---

## Metadata

**Confidence breakdown:**
- Flashcard generation patterns: HIGH — tool_use pattern verified from Phase 3 research; Flashcard model fields verified from models.py and migration
- Struggle signal detection (deterministic): HIGH — ConceptSource/Source/Chunk join paths verified; field names confirmed
- Struggle signal detection (STRUGGLE-01 embedding): MEDIUM — OpenAI embed pattern verified; pairwise cosine in Python is assumed approach
- Quiz generation: HIGH — D-15 through D-19 explicitly specify the complete implementation; tool_use pattern verified
- Quiz answer mutation (flag_modified): MEDIUM-HIGH — standard SQLAlchemy 2.0 behavior; single point of failure if assumption is wrong
- API endpoint patterns: HIGH — ingest.py and courses.py provide exact patterns to follow

**Research date:** 2026-04-25
**Valid until:** 2026-05-25 (stable stack; anthropic SDK minor versions may change)
