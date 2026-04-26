# Phase 4: Flashcards, Struggle & Quiz — Pattern Map

**Mapped:** 2026-04-25
**Files analyzed:** 9 (2 new pipeline modules, 1 new API router, 1 new schema module, 2 modified files, 3 new test files)
**Analogs found:** 9 / 9

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `backend/app/pipeline/flashcards.py` | service | batch + request-response | `backend/app/pipeline/parsers.py` lines 104–153 + `backend/app/pipeline/pipeline.py` | exact — AsyncAnthropic, asyncio.Semaphore, session-per-stage |
| `backend/app/pipeline/signals.py` | service | CRUD + batch | `backend/app/pipeline/pipeline.py` `_stage_embed` lines 161–191 | role-match — session-per-stage, OpenAI embed, SA update |
| `backend/app/api/quiz.py` | controller | request-response | `backend/app/api/ingest.py` + `backend/app/api/courses.py` | exact — APIRouter, AsyncSessionLocal direct, insert().returning() |
| `backend/app/schemas/quiz.py` | model | — | `backend/app/schemas/courses.py` + `backend/app/schemas/ingest.py` | exact — Pydantic BaseModel, model_config from_attributes |
| `backend/app/pipeline/pipeline.py` | service (orchestrator) | request-response | self — stub functions lines 215–222 | exact — stubs being replaced with lazy-import calls |
| `backend/app/api/router.py` | config | — | self — lines 1–9 | exact — include_router pattern |
| `backend/tests/test_flashcards.py` | test | — | `backend/tests/test_pipeline.py` | exact — AsyncMock/MagicMock, patch, inspect.getsource |
| `backend/tests/test_signals.py` | test | — | `backend/tests/test_pipeline.py` | exact — same mock pattern |
| `backend/tests/test_quiz_api.py` | test | — | `backend/tests/test_pipeline.py` + conftest.py client fixture | exact — AsyncMock + httpx AsyncClient for route tests |

---

## Pattern Assignments

### `backend/app/pipeline/flashcards.py` (service, batch + request-response)

**Analog:** `backend/app/pipeline/parsers.py` (AsyncAnthropic pattern) + `backend/app/pipeline/pipeline.py` (session-per-stage, API key guard, Semaphore)

**Imports pattern** — combine parsers.py lazy anthropic import with pipeline.py SA imports:
```python
from __future__ import annotations

import asyncio
import anthropic
import sqlalchemy as sa
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Concept, ConceptSource, Flashcard
```

**API key guard pattern** (pipeline.py lines 162–163):
```python
async def run_flashcards(source_id: int) -> None:
    if not settings.anthropic_api_key:
        return  # Skip in dev without key — matches _stage_embed guard
```

**AsyncAnthropic client instantiation** (parsers.py lines 112–113):
```python
import anthropic  # lazy import inside function body
client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
```

**asyncio.Semaphore + asyncio.gather pattern** (03-PATTERNS.md extractor pattern, adapted to Semaphore(3)):
```python
sem = asyncio.Semaphore(3)  # D-05: max 3 parallel LLM calls

async def generate_one(concept: Concept) -> None:
    async with sem:
        if concept.flashcards:  # D-04 idempotency check
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

**Session-per-stage concept query with selectinload** (pipeline.py lines 50–55 pattern + idempotency requirement):
```python
async with AsyncSessionLocal() as session:
    result = await session.execute(
        sa.select(Concept)
        .join(ConceptSource, ConceptSource.concept_id == Concept.id)
        .where(ConceptSource.source_id == source_id)
        .options(selectinload(Concept.flashcards))  # REQUIRED for D-04 idempotency in async
    )
    concepts = result.scalars().unique().all()  # .unique() prevents duplicates from JOIN
```

**tool_use call pattern** (parsers.py lines 122–153 adapted, 03-PATTERNS.md extractor core pattern):
```python
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
else:
    cards = []
```

**FLASHCARD_TOOL schema** (03-PATTERNS.md tool schema convention with additionalProperties: false):
```python
FLASHCARD_TOOL = {
    "name": "generate_flashcards",
    "description": "Generate study flashcards for this concept...",
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
                        "front": {"type": "string"},
                        "back": {"type": "string"},
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
```

**Error handling** — no try/except in stage function; let exceptions bubble to run_pipeline (pipeline.py lines 40–43):
```python
# pipeline.py catches ALL stage exceptions at the top level:
except Exception:
    await _stage_set_error(source_id, traceback.format_exc())
# flashcards.py does NOT catch — it raises up to run_pipeline
```

---

### `backend/app/pipeline/signals.py` (service, CRUD + batch)

**Analog:** `backend/app/pipeline/pipeline.py` `_stage_embed` (lines 161–191) for session-per-stage + OpenAI embed; `backend/app/pipeline/pipeline.py` `_stage_set_processing` for SA update pattern

**Imports pattern**:
```python
from __future__ import annotations

import math
import sqlalchemy as sa
from openai import AsyncOpenAI
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified  # REQUIRED for JSON mutation

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Chunk, Concept, ConceptSource, Source
```

**API key guard + concept query by source_id** (pipeline.py lines 162–175, D-07 scope):
```python
async def run_signals(source_id: int) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Concept)
            .join(ConceptSource, ConceptSource.concept_id == Concept.id)
            .where(ConceptSource.source_id == source_id)
            .options(selectinload(Concept.concept_sources).selectinload(ConceptSource.source))
        )
        concepts = result.scalars().unique().all()
```

**SA update + flag_modified pattern** (critical — no analog in existing codebase, but SA update style matches pipeline.py lines 53–55):
```python
# flag_modified is REQUIRED: SQLAlchemy JSON type does not track nested dict mutations
from sqlalchemy.orm.attributes import flag_modified

async with AsyncSessionLocal() as session:
    result = await session.execute(
        sa.select(Concept).where(Concept.id == concept_id)
    )
    concept = result.scalar_one()
    concept.struggle_signals = signals  # only include evaluated keys (D-11)
    flag_modified(concept, "struggle_signals")
    await session.commit()
```

**OpenAI embed client pattern** (pipeline.py lines 164–165 + 181–186):
```python
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
embed_resp = await openai_client.embeddings.create(
    model="text-embedding-3-small",
    input=all_questions,  # list of question strings
)
vectors = [e.embedding for e in embed_resp.data]
```

**STRUGGLE-03 string search** (deterministic, no LLM — purely Python):
```python
GOTCHA_PHRASES = ["actually,", "common mistake,", "be careful,", "a subtle point"]

# ConceptSource → Source → Chunk join path (D-09)
async with AsyncSessionLocal() as session:
    result = await session.execute(
        sa.select(Chunk.text)
        .join(Source, Source.id == Chunk.source_id)
        .join(ConceptSource, ConceptSource.source_id == Source.id)
        .where(ConceptSource.concept_id == concept.id)
    )
    chunk_texts = [row.text for row in result.all()]

gotcha_dense = any(
    phrase in text.lower()
    for text in chunk_texts
    for phrase in GOTCHA_PHRASES
)
```

**STRUGGLE-04 metadata check** (deterministic — Source.source_metadata field name from models.py line 59):
```python
# Source.source_metadata is mapped to "metadata" column (models.py line 59)
practice_failure = any(
    (cs.source.source_metadata or {}).get("problem_incorrect") is True
    for cs in concept.concept_sources
)
```

**Cosine similarity helper** (math stdlib — no external dep):
```python
def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
```

**Signals dict — only include evaluated keys** (D-11):
```python
# NEVER initialize with False for all keys — omit unevaluated keys entirely
signals: dict = {}
if gotcha_dense is not None:
    signals["gotcha_dense"] = gotcha_dense
if practice_failure is not None:
    signals["practice_failure"] = practice_failure
if retention_gap is not None:
    signals["retention_gap"] = retention_gap
if repeated_confusion is not None:
    signals["repeated_confusion"] = repeated_confusion
```

---

### `backend/app/api/quiz.py` (controller, request-response)

**Analog:** `backend/app/api/ingest.py` (APIRouter, AsyncSessionLocal direct, insert().returning()) + `backend/app/api/courses.py` (response_model, HTTPException, course-scoped query)

**Imports pattern** (ingest.py lines 1–17 + courses.py lines 1–14):
```python
from __future__ import annotations

import anthropic
import sqlalchemy as sa
from fastapi import APIRouter, HTTPException
from sqlalchemy import insert
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Concept, ConceptSource, Quiz
from app.schemas.quiz import QuizCreate, QuizResponse, AnswerRequest, AnswerResponse

router = APIRouter()
```

**Direct AsyncSessionLocal pattern** (ingest.py lines 115–127 — NOT Depends(get_session)):
```python
# ingest.py uses AsyncSessionLocal directly — not Depends — for background-like ops
async with AsyncSessionLocal() as session:
    result = await session.execute(
        insert(Source).values(
            course_id=course_id,
            source_type=kind,
            ...
        ).returning(Source.id)
    )
    source_id = result.scalar_one()
    await session.commit()
```

**insert().returning() pattern** (ingest.py lines 116–126):
```python
async with AsyncSessionLocal() as session:
    result = await session.execute(
        insert(Quiz).values(
            course_id=body.course_id,
            questions=questions,
        ).returning(Quiz.id)
    )
    quiz_id = result.scalar_one()
    await session.commit()
```

**HTTPException pattern** (courses.py `match_course` — returns None or raises):
```python
if not concepts:
    raise HTTPException(404, "No concepts found for this course")

# scalar_one_or_none → 404 pattern (courses.py line 88):
quiz = result.scalar_one_or_none()
if not quiz:
    raise HTTPException(404, "Quiz not found")
```

**flag_modified for JSON mutation** (no existing codebase analog — first JSON mutation in project):
```python
from sqlalchemy.orm.attributes import flag_modified

# CRITICAL: must call before commit when mutating JSON column in-place
target_q["answered"] = True
target_q["answer"] = body.answer
target_q["grading"] = grading
flag_modified(quiz, "questions")  # tell SQLAlchemy this JSON column is dirty
await session.commit()
```

**route decorator pattern** (courses.py lines 33–34, ingest.py line 65):
```python
@router.post("", response_model=QuizResponse, status_code=201)
async def create_quiz(body: QuizCreate):
    ...

@router.get("/{quiz_id}/results")
async def quiz_results(quiz_id: int):
    ...

@router.post("/{quiz_id}/answer")
async def answer_question(quiz_id: int, body: AnswerRequest):
    ...
```

**reference_answer stripping helper** (must be called in all 3 response paths):
```python
def _strip_reference_answers(questions: list[dict]) -> list[dict]:
    return [
        {k: v for k, v in q.items() if k != "reference_answer"}
        for q in (questions or [])
    ]
```

**QUIZ_TOOL and GRADE_TOOL schemas** (same additionalProperties: false convention as all Phase 3 tools):
```python
# Single LLM call for all questions (D-15); tool_choice forces tool response
QUIZ_TOOL = {
    "name": "generate_quiz",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["questions"],
        "properties": {"questions": {"type": "array", "items": {...}}}
    }
}

GRADE_TOOL = {
    "name": "grade_answer",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["correct", "feedback"],
        "properties": {
            "correct": {"type": "boolean"},
            "feedback": {"type": "string"}
        }
    }
}
```

---

### `backend/app/schemas/quiz.py` (model, —)

**Analog:** `backend/app/schemas/courses.py` (BaseModel + model_config) + `backend/app/schemas/ingest.py` (request/response split)

**Imports pattern** (courses.py lines 1–4):
```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel
```

**Request schema pattern** (courses.py `CourseCreate`, ingest.py `IngestTextBody`):
```python
class QuizCreate(BaseModel):
    course_id: int
    num_questions: int


class AnswerRequest(BaseModel):
    question_id: int
    answer: str
```

**Response schema pattern** (courses.py `CourseResponse` with `model_config`):
```python
class QuizResponse(BaseModel):
    id: int
    course_id: int
    questions: list[dict[str, Any]]  # reference_answer stripped before populating

    model_config = {"from_attributes": True}


class AnswerResponse(BaseModel):
    grading: dict[str, Any]
    next_question: dict[str, Any] | None = None
    is_complete: bool = False
    score: float | None = None
    correct_count: int | None = None
    total: int | None = None
    concepts_to_review: list[int] | None = None
```

---

### `backend/app/pipeline/pipeline.py` (modified orchestrator)

**Analog:** self — existing stubs lines 215–222 being replaced

**Stubs to replace** (pipeline.py lines 215–222):
```python
# BEFORE (Phase 2 stubs — these two functions are replaced):
async def _stage_flashcards_stub(source_id: int) -> None:
    """Flashcard generation stub — Phase 4 will create flashcard nodes per concept."""
    pass

async def _stage_signals_stub(source_id: int) -> None:
    """Struggle signal stub — Phase 4 will detect and store struggle signals."""
    pass
```

**Replacement lazy-import pattern** (pipeline.py lines 63–64 for parsers — follow same style):
```python
# pipeline.py lines 63–64 — existing lazy import style to follow:
from app.pipeline.parsers import parse_pdf, parse_url, parse_image, parse_text

# Phase 4 replacements follow same lazy-import pattern:
async def _stage_flashcards_stub(source_id: int) -> None:
    from app.pipeline.flashcards import run_flashcards
    await run_flashcards(source_id)

async def _stage_signals_stub(source_id: int) -> None:
    from app.pipeline.signals import run_signals
    await run_signals(source_id)
```

Note: The stub function *names* in `run_pipeline()` call sites (lines 37–38) stay unchanged — only the function bodies are replaced with real dispatch calls.

---

### `backend/app/api/router.py` (modified config)

**Analog:** self — lines 1–9

**Current content** (router.py lines 1–9):
```python
from fastapi import APIRouter

from app.api import health, courses, ingest

router = APIRouter()

router.include_router(health.router, tags=["health"])
router.include_router(courses.router, prefix="/courses", tags=["courses"])
router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
```

**Addition to make** (follow exact pattern of existing include_router calls):
```python
from app.api import health, courses, ingest, quiz  # add quiz

router.include_router(quiz.router, prefix="/quiz", tags=["quiz"])
```

---

### `backend/tests/test_flashcards.py` (test)

**Analog:** `backend/tests/test_pipeline.py`

**File header + imports pattern** (test_pipeline.py lines 1–26):
```python
"""Tests for flashcards.py pipeline stage (Phase 4).

Covers FLASH-01 through FLASH-06.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.pipeline.flashcards import run_flashcards
```

**Mock tool_use response helper** (test_pipeline.py `_make_source` helper pattern adapted for Anthropic):
```python
def _make_tool_response_flashcards(cards: list[dict]) -> MagicMock:
    """Build a mock Anthropic messages.create response with tool_use content."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = {"cards": cards}
    message = MagicMock()
    message.stop_reason = "tool_use"
    message.content = [tool_block]
    return message
```

**Session mock structure** (test_pipeline.py lines 189–217 — standard mock):
```python
mock_session = AsyncMock()
mock_session.__aenter__ = AsyncMock(return_value=mock_session)
mock_session.__aexit__ = AsyncMock(return_value=False)
mock_result = MagicMock()
mock_result.scalars.return_value.unique.return_value.all.return_value = [concept]
mock_session.execute = AsyncMock(return_value=mock_result)
mock_session.commit = AsyncMock()
mock_session.add = MagicMock()
```

**patch target convention** (test_pipeline.py lines 85–93 — full module path):
```python
with patch("app.pipeline.flashcards.AsyncSessionLocal", return_value=mock_session):
    with patch("app.pipeline.flashcards.anthropic.AsyncAnthropic") as mock_anthropic_cls:
        mock_client = AsyncMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=_make_tool_response_flashcards([...]))
        await run_flashcards(source_id=1)
```

**async test decorator pattern** (test_pipeline.py lines 73–97 — explicit decorator for clarity):
```python
@pytest.mark.asyncio
async def test_flashcard_generation():
    ...
```

**Module-level structural inspection pattern** (test_pipeline.py lines 258–308):
```python
def test_flashcards_uses_semaphore():
    import inspect
    import app.pipeline.flashcards as mod
    source = inspect.getsource(mod)
    assert "asyncio.Semaphore(3)" in source

def test_flashcards_uses_tool_choice():
    import inspect
    import app.pipeline.flashcards as mod
    source = inspect.getsource(mod)
    assert "tool_choice" in source
    assert "generate_flashcards" in source

def test_no_srs_columns():
    """Flashcard model has no due_at, ease_factor, or repetitions (FLASH-06)."""
    from app.models.models import Flashcard
    assert not hasattr(Flashcard, "due_at")
    assert not hasattr(Flashcard, "ease_factor")
    assert not hasattr(Flashcard, "repetitions")
```

---

### `backend/tests/test_signals.py` (test)

**Analog:** `backend/tests/test_pipeline.py`

**File header + imports**:
```python
"""Tests for signals.py pipeline stage (Phase 4).

Covers STRUGGLE-01 through STRUGGLE-05.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.pipeline.signals import run_signals
```

**Mock concept + concept_source helper** (test_pipeline.py `_make_source` pattern):
```python
def _make_concept(id: int = 1, struggle_signals: dict | None = None):
    c = MagicMock()
    c.id = id
    c.struggle_signals = struggle_signals
    c.concept_sources = []
    return c

def _make_concept_source(concept_id: int = 1, source_id: int = 1, source_type: str = "pdf"):
    cs = MagicMock()
    cs.concept_id = concept_id
    cs.source_id = source_id
    cs.source = MagicMock()
    cs.source.source_type = source_type
    cs.source.source_metadata = {}
    cs.source.created_at = MagicMock()
    cs.student_questions = []
    return cs
```

**flag_modified assertion pattern** (verify it is called for JSON mutation):
```python
with patch("sqlalchemy.orm.attributes.flag_modified") as mock_flag_modified:
    with patch("app.pipeline.signals.AsyncSessionLocal", return_value=mock_session):
        await run_signals(source_id=1)
    mock_flag_modified.assert_called()
```

**Deterministic signal test** (no async needed — pure Python logic):
```python
def test_gotcha_dense_detects_phrases():
    """STRUGGLE-03: any gotcha phrase in chunk text triggers gotcha_dense=True."""
    from app.pipeline.signals import GOTCHA_PHRASES
    text = "actually, this is a common misconception"
    assert any(phrase in text.lower() for phrase in GOTCHA_PHRASES)
```

---

### `backend/tests/test_quiz_api.py` (test)

**Analog:** `backend/tests/test_pipeline.py` (mock patterns) + `backend/tests/conftest.py` (client fixture for route tests)

**File header + imports**:
```python
"""Tests for quiz API endpoints (Phase 4).

Covers QUIZ-01 through QUIZ-06.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
```

**httpx client fixture usage** (conftest.py lines 9–16 — already defined):
```python
# conftest.py provides the `client` fixture:
@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

# Test uses it:
@pytest.mark.asyncio
async def test_create_quiz(client):
    with patch("app.api.quiz.AsyncSessionLocal", return_value=mock_session):
        resp = await client.post("/quiz", json={"course_id": 1, "num_questions": 5})
    assert resp.status_code == 201
```

**Mock quiz object for JSON mutation test**:
```python
def _make_quiz(id: int = 1, course_id: int = 1, questions: list | None = None):
    q = MagicMock()
    q.id = id
    q.course_id = course_id
    q.questions = questions or []
    return q
```

**reference_answer stripping test** (structural — no mock needed):
```python
def test_no_reference_answer_in_quiz_response():
    """reference_answer must never appear in any API response (QUIZ-05 security)."""
    from app.api.quiz import _strip_reference_answers
    questions = [{"type": "short_answer", "question": "Q?", "reference_answer": "secret", "answered": False}]
    stripped = _strip_reference_answers(questions)
    assert "reference_answer" not in stripped[0]
    assert "question" in stripped[0]  # other fields preserved
```

**Session mock for route handler** (test_pipeline.py lines 189–217):
```python
mock_session = AsyncMock()
mock_session.__aenter__ = AsyncMock(return_value=mock_session)
mock_session.__aexit__ = AsyncMock(return_value=False)
mock_result = MagicMock()
mock_result.scalar_one.return_value = 42  # quiz_id returned by insert().returning()
mock_result.scalar_one_or_none.return_value = _make_quiz()
mock_session.execute = AsyncMock(return_value=mock_result)
mock_session.commit = AsyncMock()
```

---

## Shared Patterns

### AsyncAnthropic Client + tool_use
**Source:** `backend/app/pipeline/parsers.py` lines 112–113 (client instantiation); 03-PATTERNS.md (tool_use forcing)
**Apply to:** `flashcards.py` (flashcard generation), `quiz.py` (quiz generation + free-response grading)
```python
import anthropic
client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

# Always force tool use — prevents end_turn fallback with no tool block:
tool_choice={"type": "tool", "name": "generate_flashcards"}

# Extract without json.loads — tool_block.input is already a Python dict:
if message.stop_reason == "tool_use":
    tool_block = next(b for b in message.content if b.type == "tool_use")
    data = tool_block.input  # Python dict, not JSON string
```

### Session-Per-Stage Pattern
**Source:** `backend/app/pipeline/pipeline.py` — every stage function (`_stage_set_processing` lines 50–55, `_stage_embed` lines 161–191)
**Apply to:** `flashcards.py`, `signals.py`
```python
# Each stage opens its own AsyncSessionLocal — NEVER pass session across stage boundaries
async with AsyncSessionLocal() as session:
    result = await session.execute(sa.select(...).where(...))
    items = result.scalars().all()
    # ... mutations ...
    await session.commit()
# expire_on_commit=False (database.py line 14) — objects accessible after commit
```

### API Key Guard
**Source:** `backend/app/pipeline/pipeline.py` lines 162–163
**Apply to:** `flashcards.py` (anthropic_api_key), `signals.py` (openai_api_key for STRUGGLE-01)
```python
if not settings.anthropic_api_key:
    return  # skip stage silently — matches _stage_embed guard
if not settings.openai_api_key:
    return  # skip STRUGGLE-01 silently
```

### Direct AsyncSessionLocal in API routes (not Depends)
**Source:** `backend/app/api/ingest.py` lines 115–127; `backend/app/api/courses.py` lines 73–86
**Apply to:** `quiz.py` all three routes
```python
# ingest.py uses direct AsyncSessionLocal for insert operations (not Depends)
# courses.py uses AsyncSessionLocal for the match endpoint (background-like)
# quiz.py follows same pattern — direct context manager, not dependency injection
async with AsyncSessionLocal() as session:
    ...
```

### Error Handling (no try/except in pipeline stages)
**Source:** `backend/app/pipeline/pipeline.py` lines 40–43
**Apply to:** `flashcards.py`, `signals.py`
```python
# run_pipeline catches all exceptions at the top level — stages do NOT catch
# Exception: quiz.py API routes use HTTPException for user-facing errors
try:
    await _stage_flashcards_stub(source_id)
    ...
except Exception:
    await _stage_set_error(source_id, traceback.format_exc())
```

### flag_modified for JSON Column Mutation
**Source:** SQLAlchemy 2.0 standard — no existing codebase analog (first JSON mutation in project)
**Apply to:** `signals.py` (struggle_signals update), `quiz.py` (questions mutation in POST /quiz/{id}/answer)
```python
from sqlalchemy.orm.attributes import flag_modified

# REQUIRED after any in-place dict/list mutation on a JSON column:
concept.struggle_signals = signals
flag_modified(concept, "struggle_signals")
await session.commit()

# Same pattern in quiz answer handler:
quiz.questions[i]["answered"] = True
flag_modified(quiz, "questions")
await session.commit()
```

### Test Mock Session Structure
**Source:** `backend/tests/test_pipeline.py` lines 189–217
**Apply to:** `test_flashcards.py`, `test_signals.py`, `test_quiz_api.py`
```python
mock_session = AsyncMock()
mock_session.__aenter__ = AsyncMock(return_value=mock_session)
mock_session.__aexit__ = AsyncMock(return_value=False)
mock_session.execute = AsyncMock(return_value=MagicMock())
mock_session.commit = AsyncMock()
mock_session.flush = AsyncMock()
mock_session.add = MagicMock()

# Patch by full module path — same convention as test_pipeline.py:
with patch("app.pipeline.flashcards.AsyncSessionLocal", return_value=mock_session):
    ...
```

### Pydantic Schema Convention
**Source:** `backend/app/schemas/courses.py` lines 1–22; `backend/app/schemas/ingest.py` lines 1–27
**Apply to:** `backend/app/schemas/quiz.py`
```python
from pydantic import BaseModel

class SomethingResponse(BaseModel):
    id: int
    # ...
    model_config = {"from_attributes": True}  # for ORM → Pydantic serialization
```

### ORM Field Names — Phase 4 Models
**Source:** `backend/app/models/models.py`
**Apply to:** All Phase 4 files — use these exact field names:

| Model | Fields Used in Phase 4 | Notes |
|-------|------------------------|-------|
| `Concept` | `id`, `course_id`, `title`, `definition`, `gotchas`, `related_concepts`, `struggle_signals`, `flashcards` (relationship) | `struggle_signals` is JSON |
| `ConceptSource` | `concept_id`, `source_id`, `student_questions`, `source` (relationship) | `student_questions` is JSON list |
| `Source` | `id`, `source_type`, `source_metadata`, `created_at` | `source_metadata` Python attr maps to "metadata" DB column (line 59) |
| `Flashcard` | `id`, `concept_id`, `front`, `back`, `card_type`, `created_at` | No SRS columns |
| `Quiz` | `id`, `course_id`, `questions`, `created_at` | `questions` is JSON list |
| `Chunk` | `id`, `source_id`, `text` | for STRUGGLE-03 chunk text scan |

---

## No Analog Found

All 9 files have close analogs. Two patterns have no existing codebase precedent and rely on research:

| Pattern | Used By | Source |
|---------|---------|--------|
| `flag_modified(model, "field")` for JSON mutation | `signals.py`, `quiz.py` | SQLAlchemy 2.0 standard; no existing JSON mutation in codebase. **Verify in Wave 0 test.** |
| `selectinload(...).selectinload(...)` chained eager load | `signals.py` | Standard SQLAlchemy; async requires eager loading to avoid MissingGreenlet |

---

## Metadata

**Analog search scope:** `backend/app/pipeline/`, `backend/app/api/`, `backend/app/schemas/`, `backend/app/models/`, `backend/app/core/`, `backend/tests/`, `.planning/phases/03-extraction-resolution-edges/03-PATTERNS.md`
**Files scanned:** 12 primary files read in full
**Pattern extraction date:** 2026-04-25
