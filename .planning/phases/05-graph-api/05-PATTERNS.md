# Phase 5: Graph API — Pattern Map

**Mapped:** 2026-04-25
**Files analyzed:** 6 new/modified files
**Analogs found:** 6 / 6

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/app/api/courses.py` | controller | CRUD + request-response | `backend/app/api/courses.py` (self) | self — extend |
| `backend/app/api/concepts.py` | controller | CRUD + request-response | `backend/app/api/courses.py` | exact role-match |
| `backend/app/api/router.py` | config | request-response | `backend/app/api/router.py` (self) | self — extend |
| `backend/app/schemas/graph.py` | model (Pydantic) | transform | `backend/app/schemas/courses.py` | exact role-match |
| `backend/app/schemas/concepts.py` | model (Pydantic) | transform | `backend/app/schemas/courses.py` | exact role-match |
| `backend/tests/test_graph_api.py` | test | request-response | `backend/tests/test_courses.py` | exact |
| `backend/tests/test_concept_detail.py` | test | request-response | `backend/tests/test_courses.py` | exact |

---

## Pattern Assignments

### `backend/app/api/courses.py` — extend with `GET /courses/{course_id}/graph`

**Analog:** self — existing file extended with a new route

**Imports pattern** (lines 1–13 of existing file — keep all, add new model imports):
```python
from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_session
from app.models.models import Course, Concept, Flashcard, Quiz, Edge  # add Concept, Flashcard, Quiz, Edge
from app.schemas.courses import CourseCreate, CourseMatchResponse, CourseResponse
from app.schemas.graph import GraphResponse  # add this import
```

**Existing GET list pattern** (lines 21–26 — verbatim, reference only):
```python
@router.get("", response_model=list[CourseResponse])
async def list_courses(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        sa.select(Course).where(Course.user_id == 1).order_by(Course.created_at)
    )
    return result.scalars().all()
```

**Core pattern for new `GET /{course_id}/graph` route:**

Route must be added AFTER the `/match` route and AFTER `POST ""` — FastAPI matches in registration order. `/match` is already registered before any `/{id}` route (line 52 in existing file); `/{course_id}/graph` must come after `/match` to avoid shadowing it.

```python
# ---------------------------------------------------------------------------
# GET /courses/{course_id}/graph — assemble full graph payload
# ---------------------------------------------------------------------------

@router.get("/{course_id}/graph", response_model=GraphResponse)
async def get_course_graph(
    course_id: int,
    session: AsyncSession = Depends(get_session),   # same Depends(get_session) as all other routes
):
    # 1. Load course row (validates ownership via user_id=1)
    course_result = await session.execute(
        sa.select(Course).where(Course.id == course_id, Course.user_id == 1)
    )
    course = course_result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    # 2. Load all concepts for this course (single query)
    concepts_result = await session.execute(
        sa.select(Concept).where(Concept.course_id == course_id)
    )
    concepts = concepts_result.scalars().all()
    concept_ids = [c.id for c in concepts]

    # 3. Flashcards — single IN query across all concept IDs (no N+1)
    if concept_ids:
        flashcards_result = await session.execute(
            sa.select(Flashcard).where(Flashcard.concept_id.in_(concept_ids))
        )
        flashcards = flashcards_result.scalars().all()
    else:
        flashcards = []

    # 4. Most recent quiz for the course (LIMIT 1)
    quiz_result = await session.execute(
        sa.select(Quiz).where(Quiz.course_id == course_id)
        .order_by(Quiz.created_at.desc()).limit(1)
    )
    quiz = quiz_result.scalar_one_or_none()

    # 5. Edges between concepts in this course — single IN query (no N+1)
    if concept_ids:
        edges_result = await session.execute(
            sa.select(Edge).where(
                Edge.from_id.in_(concept_ids),
                Edge.to_id.in_(concept_ids),
            )
        )
        edges = edges_result.scalars().all()
    else:
        edges = []

    # 6. Assemble payload in Python (virtual nodes + synthetic contains edges)
    return _build_graph_payload(course, concepts, flashcards, quiz, edges)
```

**Graph assembly helper — add below route function:**
```python
def _build_graph_payload(course, concepts, flashcards, quiz, edges) -> dict:
    """Assemble GraphResponse dict from ORM objects.

    - Course root node is virtual: synthesized from courses table row.
    - "contains" edges are synthetic: derived from concept.course_id FK and
      flashcard.concept_id FK. The edges table has NO contains rows (Phase 3
      EDGE-01 design decision).
    - All node IDs are prefixed strings to avoid cross-type collisions in React Flow.
    - Embedding vectors are NEVER included in node data (50KB bloat per concept).
    """
    nodes = []
    graph_edges = []

    course_node_id = f"course-{course.id}"

    # Course root node (virtual)
    nodes.append({
        "id": course_node_id,
        "type": "course",
        "data": {"label": course.title, "course_id": course.id, "description": course.description},
    })

    # Concept nodes + synthetic course→concept "contains" edges
    fc_count_by_concept: dict[int, int] = {}
    for c in concepts:
        concept_node_id = f"concept-{c.id}"
        nodes.append({
            "id": concept_node_id,
            "type": "concept",
            "data": {
                "label": c.title,
                "concept_id": c.id,
                "depth": c.depth,
                "has_struggle_signals": bool(c.struggle_signals),
                "struggle_signals": c.struggle_signals,
                "flashcard_count": 0,   # updated below after flashcard pass
            },
        })
        graph_edges.append({
            "id": f"contains-{course.id}-{c.id}",
            "source": course_node_id,
            "target": concept_node_id,
            "type": "contains",
            "data": {},
        })

    # Flashcard nodes + synthetic concept→flashcard "contains" edges
    for f in flashcards:
        flashcard_node_id = f"flashcard-{f.id}"
        parent_node_id = f"concept-{f.concept_id}"
        nodes.append({
            "id": flashcard_node_id,
            "type": "flashcard",
            "data": {
                "label": f.front[:60],
                "flashcard_id": f.id,
                "front": f.front,
                "back": f.back,
                "card_type": f.card_type,
            },
        })
        graph_edges.append({
            "id": f"contains-fc-{f.id}",
            "source": parent_node_id,
            "target": flashcard_node_id,
            "type": "contains",
            "data": {},
        })
        fc_count_by_concept[f.concept_id] = fc_count_by_concept.get(f.concept_id, 0) + 1

    # Backfill flashcard_count on concept nodes now that we have the tally
    for node in nodes:
        if node["type"] == "concept":
            cid = node["data"]["concept_id"]
            node["data"]["flashcard_count"] = fc_count_by_concept.get(cid, 0)

    # Quiz node + synthetic course→quiz "contains" edge
    if quiz is not None:
        quiz_node_id = f"quiz-{quiz.id}"
        nodes.append({
            "id": quiz_node_id,
            "type": "quiz",
            "data": {
                "label": "Quiz",
                "quiz_id": quiz.id,
                "question_count": len(quiz.questions) if quiz.questions else 0,
            },
        })
        graph_edges.append({
            "id": f"contains-quiz-{quiz.id}",
            "source": course_node_id,
            "target": quiz_node_id,
            "type": "contains",
            "data": {},
        })

    # Real edges from edges table (co_occurrence, prerequisite, related)
    for e in edges:
        graph_edges.append({
            "id": f"edge-{e.id}",
            "source": f"concept-{e.from_id}",
            "target": f"concept-{e.to_id}",
            "type": e.edge_type,
            "data": {"weight": e.weight},
        })

    return {"nodes": nodes, "edges": graph_edges}
```

**`/courses/match` consistency fix** (lines 52–95 of existing file):

The existing implementation opens `AsyncSessionLocal()` directly inside the endpoint instead of using the injected `session` dependency. Fix by replacing:
```python
# BEFORE (inconsistent — opens second connection)
async with AsyncSessionLocal() as session:
    result = await session.execute(...)

# AFTER (consistent — use injected dependency)
# Change signature: async def match_course(hint: str, session: AsyncSession = Depends(get_session)):
# Then query directly:
result = await session.execute(...)
```

Also add `hint = hint[:500]` truncation before calling OpenAI (DoS mitigation per security domain).

---

### `backend/app/api/concepts.py` — new file

**Analog:** `backend/app/api/courses.py` (exact role match — same FastAPI router pattern, same Depends(get_session), same HTTPException 404 guard)

**Full file pattern to copy from analog:**

```python
from __future__ import annotations

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.models import Concept, ConceptSource, Source, Flashcard
from app.schemas.concepts import ConceptDetailResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /concepts/{concept_id} — full concept detail
# ---------------------------------------------------------------------------

@router.get("/{concept_id}", response_model=ConceptDetailResponse)
async def get_concept_detail(
    concept_id: int,
    session: AsyncSession = Depends(get_session),   # copy verbatim from courses.py
):
    # Load concept (same scalar_one_or_none + 404 guard as courses.py)
    result = await session.execute(
        sa.select(Concept).where(Concept.id == concept_id)
    )
    concept = result.scalar_one_or_none()
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    # Validate concept belongs to a course owned by user_id=1 (ID enumeration guard)
    # Join through course to check ownership
    course_check = await session.execute(
        sa.select(sa.func.count())
        .select_from(Concept)
        .join(sa.text("courses"), sa.text("concepts.course_id = courses.id"))
        .where(
            sa.text("concepts.id = :cid AND courses.user_id = 1"),
        ).params(cid=concept_id)
    )
    # Simpler alternative using ORM (prefer this):
    from app.models.models import Course
    ownership = await session.execute(
        sa.select(Course.id)
        .join(Concept, Concept.course_id == Course.id)
        .where(Concept.id == concept_id, Course.user_id == 1)
    )
    if ownership.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    # Load concept_sources joined with sources (single query, not N+1)
    cs_result = await session.execute(
        sa.select(ConceptSource, Source)
        .join(Source, ConceptSource.source_id == Source.id)
        .where(ConceptSource.concept_id == concept_id)
    )
    cs_rows = cs_result.all()

    # Aggregate student_questions (chat_log sources only)
    student_questions: list[str] = []
    source_citations: list[dict] = []
    for cs, source in cs_rows:
        if source.source_type == "chat_log" and cs.student_questions:
            student_questions.extend(cs.student_questions)
        source_citations.append({
            "source_id": source.id,
            "title": source.title,
            "source_type": source.source_type,
        })

    # Flashcard count (scalar aggregate — no object load needed)
    fc_result = await session.execute(
        sa.select(sa.func.count()).select_from(Flashcard)
        .where(Flashcard.concept_id == concept_id)
    )
    flashcard_count = fc_result.scalar_one()

    # Build response explicitly — do NOT use from_attributes here because
    # Concept.definition must map to response field "summary" (rename at construction)
    return ConceptDetailResponse(
        id=concept.id,
        course_id=concept.course_id,
        title=concept.title,
        summary=concept.definition,         # CRITICAL: field rename definition→summary
        key_points=concept.key_points or [],
        gotchas=concept.gotchas or [],
        examples=concept.examples or [],
        student_questions=student_questions,
        source_citations=source_citations,
        flashcard_count=flashcard_count,
        struggle_signals=concept.struggle_signals,
        depth=concept.depth,
    )
```

---

### `backend/app/api/router.py` — extend to register concepts router

**Analog:** self — existing 9-line file

**Current file** (lines 1–9):
```python
from fastapi import APIRouter
from app.api import health, courses, ingest

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(courses.router, prefix="/courses", tags=["courses"])
router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
```

**Modified file — add concepts import and include_router:**
```python
from fastapi import APIRouter
from app.api import health, courses, ingest, concepts   # add concepts

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(courses.router, prefix="/courses", tags=["courses"])
router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
router.include_router(concepts.router, prefix="/concepts", tags=["concepts"])  # add line
```

---

### `backend/app/schemas/graph.py` — new file

**Analog:** `backend/app/schemas/courses.py` (exact role match — Pydantic v2 BaseModel, no `from_attributes` needed since GraphResponse is built explicitly from dicts)

**Full file:**
```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str               # prefixed string: "course-{id}", "concept-{id}", "flashcard-{id}", "quiz-{id}"
    type: str             # "course" | "concept" | "flashcard" | "quiz"
    data: dict[str, Any]  # type-specific payload; NEVER include embedding vectors here


class GraphEdge(BaseModel):
    id: str
    source: str           # node id string (prefixed)
    target: str           # node id string (prefixed)
    type: str             # "contains" | "co_occurrence" | "prerequisite" | "related"
    data: dict[str, Any] = {}


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    # No from_attributes — assembled from dicts in _build_graph_payload(), not ORM objects
```

---

### `backend/app/schemas/concepts.py` — new file

**Analog:** `backend/app/schemas/courses.py` (exact role match)

Note: `ConceptDetailResponse` does NOT use `model_config = {"from_attributes": True}` because the response is built explicitly in the endpoint (the `definition` → `summary` rename requires explicit construction, not auto-mapping).

**Full file:**
```python
from __future__ import annotations

from pydantic import BaseModel


class SourceCitation(BaseModel):
    source_id: int
    title: str | None = None
    source_type: str        # "pdf" | "url" | "image" | "text" | "chat_log"


class ConceptDetailResponse(BaseModel):
    id: int
    course_id: int
    title: str
    summary: str | None = None          # maps to Concept.definition — renamed in endpoint
    key_points: list[str] = []
    gotchas: list[str] = []
    examples: list[str] = []
    student_questions: list[str] = []   # aggregated from ConceptSource.student_questions (chat_log only)
    source_citations: list[SourceCitation] = []
    flashcard_count: int = 0
    struggle_signals: dict | None = None
    depth: int | None = None
    # NOTE: no model_config from_attributes — explicit construction in endpoint handles rename
```

---

### `backend/tests/test_graph_api.py` — new file

**Analog:** `backend/tests/test_courses.py` (exact role match — same `client` fixture, same `app.dependency_overrides[get_session]` DB mock pattern, same `AsyncMock`/`MagicMock` stack)

**Imports pattern** (copy from `test_courses.py` lines 1–8):
```python
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.database import get_session
```

**DB session override pattern** (copy from `test_courses.py` lines 19–31 — this is the canonical mock pattern for all DB-touching tests):
```python
from app.main import app
from sqlalchemy.ext.asyncio import AsyncSession

mock_session = AsyncMock(spec=AsyncSession)
mock_session.execute = AsyncMock(return_value=MagicMock(...))

async def override_get_session():
    yield mock_session

app.dependency_overrides[get_session] = override_get_session
try:
    response = await client.get("/courses")
finally:
    app.dependency_overrides.pop(get_session, None)
```

**OpenAI mock pattern** (copy from `test_courses.py` lines 114–131 — for GRAPH-07 tests):
```python
with patch("app.api.courses.settings") as mock_settings, \
     patch("app.api.courses.AsyncOpenAI") as mock_openai_cls, \
     patch("app.api.courses.AsyncSessionLocal") as mock_session_cls:

    mock_settings.openai_api_key = "sk-test"
    mock_client = AsyncMock()
    mock_client.embeddings.create = AsyncMock(return_value=mock_embed_response)
    mock_openai_cls.return_value = mock_client
    # ... mock session ...
    response = await client.get("/courses/match?hint=machine+learning")
```

**Graph endpoint test pattern — copy this structure for GRAPH-03/GRAPH-05:**
```python
async def test_graph_nodes_and_edges(client):
    """GRAPH-03 — GET /courses/{id}/graph returns nodes and edges."""
    from app.main import app
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.models import Course, Concept, Flashcard, Quiz

    # Build minimal mock ORM objects
    mock_course = MagicMock(spec=Course)
    mock_course.id = 1
    mock_course.user_id = 1
    mock_course.title = "CS 229"
    mock_course.description = None

    mock_concept = MagicMock(spec=Concept)
    mock_concept.id = 10
    mock_concept.course_id = 1
    mock_concept.title = "Gradient Descent"
    mock_concept.depth = 1
    mock_concept.struggle_signals = None
    mock_concept.definition = "An optimization algorithm"

    # Sequence mock_session.execute calls by call count or use side_effect list
    mock_session = AsyncMock(spec=AsyncSession)
    responses = [
        # call 1: SELECT course
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_course)),
        # call 2: SELECT concepts
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_concept])))),
        # call 3: SELECT flashcards WHERE concept_id IN (...)
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
        # call 4: SELECT quiz
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        # call 5: SELECT edges
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
    ]
    mock_session.execute = AsyncMock(side_effect=responses)

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        response = await client.get("/courses/1/graph")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    node_types = {n["type"] for n in data["nodes"]}
    assert "course" in node_types
    assert "concept" in node_types
```

---

### `backend/tests/test_concept_detail.py` — new file

**Analog:** `backend/tests/test_courses.py` (exact role match — identical fixture and mock patterns)

**Test structure pattern:**
```python
async def test_concept_detail_fields(client):
    """GRAPH-04 — GET /concepts/{id} returns all required detail fields."""
    from app.main import app
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_concept = MagicMock()
    mock_concept.id = 5
    mock_concept.course_id = 1
    mock_concept.title = "Gradient Descent"
    mock_concept.definition = "An iterative optimization algorithm"  # DB field name
    mock_concept.key_points = ["converges to local minimum"]
    mock_concept.gotchas = ["learning rate sensitivity"]
    mock_concept.examples = ["linear regression weight update"]
    mock_concept.struggle_signals = None
    mock_concept.depth = 2

    mock_session = AsyncMock(spec=AsyncSession)
    # Execute call sequence: concept, ownership check, concept_sources join, flashcard count
    mock_session.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_concept)),  # concept
        MagicMock(scalar_one_or_none=MagicMock(return_value=1)),              # ownership
        MagicMock(all=MagicMock(return_value=[])),                            # concept_sources
        MagicMock(scalar_one=MagicMock(return_value=3)),                      # flashcard count
    ])

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        response = await client.get("/concepts/5")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    data = response.json()
    # GRAPH-04: verify all required fields are present
    required_fields = {
        "id", "course_id", "title", "summary", "key_points", "gotchas",
        "examples", "student_questions", "source_citations", "flashcard_count",
        "struggle_signals",
    }
    assert required_fields.issubset(data.keys())
    # CRITICAL: definition→summary rename must work
    assert data["summary"] == "An iterative optimization algorithm"
    assert "definition" not in data   # old name must NOT appear in response
```

---

## Shared Patterns

### DB Session Dependency Injection

**Source:** `backend/app/core/database.py` lines 17–20 and `backend/app/api/courses.py` lines 22, 34
**Apply to:** All route functions in `courses.py` (graph route) and all routes in `concepts.py`

```python
# In every route function signature — verbatim pattern:
async def my_route(session: AsyncSession = Depends(get_session)):
    ...
```

`get_session` is imported from `app.core.database`. Do NOT open `AsyncSessionLocal()` directly inside new routes — that is the inconsistency that exists in `/courses/match` and should be cleaned up, not copied.

### `scalar_one_or_none()` + 404 Guard

**Source:** `backend/app/api/courses.py` — pattern used in `list_courses` and all single-object lookups
**Apply to:** Both the graph route (course lookup) and `concepts.py` (concept lookup)

```python
result = await session.execute(
    sa.select(Model).where(Model.id == id_param, Model.user_id == 1)
)
obj = result.scalar_one_or_none()
if obj is None:
    raise HTTPException(status_code=404, detail="<Model> not found")
```

### `scalars().all()` for Collection Queries

**Source:** `backend/app/api/courses.py` line 25
**Apply to:** All collection queries in graph assembly (concepts, flashcards, edges)

```python
result = await session.execute(sa.select(Model).where(...))
items = result.scalars().all()
```

### Pydantic v2 Schema Style

**Source:** `backend/app/schemas/courses.py` lines 11–18
**Apply to:** All new Pydantic models in `schemas/graph.py` and `schemas/concepts.py`

```python
from pydantic import BaseModel

class SomeResponse(BaseModel):
    field_a: str
    field_b: int
    field_c: str | None = None

    model_config = {"from_attributes": True}  # only when auto-mapping from ORM objects
```

Note: `GraphResponse` and `ConceptDetailResponse` are built explicitly from dicts/constructor args, so they do NOT need `model_config = {"from_attributes": True}`. `CourseResponse` uses it because FastAPI passes the ORM object directly to the response model.

### `from_attributes` Rule

**Source:** `backend/app/schemas/courses.py` line 18 (CourseResponse uses it), line 22 (CourseMatchResponse does NOT use it — built manually)
**Apply to:** Decide per-schema whether auto-mapping is used:

| Schema | from_attributes | Reason |
|---|---|---|
| `CourseResponse` | yes | ORM object passed directly to response_model |
| `CourseMatchResponse` | no | Built explicitly: `CourseMatchResponse(course_id=row.id, ...)` |
| `GraphResponse` | no | Built from dict in `_build_graph_payload()` |
| `GraphNode` | no | Dict items |
| `GraphEdge` | no | Dict items |
| `ConceptDetailResponse` | no | Explicit constructor with `summary=concept.definition` rename |
| `SourceCitation` | no | Built from dict items in endpoint |

### Test: DB Override Teardown (try/finally)

**Source:** `backend/tests/test_courses.py` lines 25–31
**Apply to:** Every test function that calls `app.dependency_overrides[get_session] = ...`

```python
app.dependency_overrides[get_session] = override_get_session
try:
    response = await client.get("/some/path")
finally:
    app.dependency_overrides.pop(get_session, None)
```

Always use `try/finally` to prevent override leakage across tests.

### Test: Router Wiring Verification

**Source:** `backend/tests/test_ingest.py` lines 239–246
**Apply to:** `test_graph_api.py` — add a wiring test for concepts router

```python
def test_concepts_router_is_registered():
    import inspect
    import app.api.router as router_mod
    source = inspect.getsource(router_mod)
    assert "concepts" in source
    assert "concepts.router" in source
```

### N+1 Prevention Pattern

**Source:** RESEARCH.md Pattern 1 (confirmed against existing `courses.py` IN-query style)
**Apply to:** Graph endpoint — flashcard load and edge load

Always use `Model.column.in_(id_list)` to batch-load collections in a single query. Never load in a loop:
```python
# CORRECT — single query
flashcards_result = await session.execute(
    sa.select(Flashcard).where(Flashcard.concept_id.in_(concept_ids))
)

# WRONG — N+1 (never do this)
for concept in concepts:
    flashcards = await session.execute(
        sa.select(Flashcard).where(Flashcard.concept_id == concept.id)
    )
```

---

## No Analog Found

All files have close analogs. No entries needed here.

---

## Anti-Pattern Register

Copied verbatim from RESEARCH.md for planner reference:

| Anti-Pattern | Detection | Fix |
|---|---|---|
| `concept.embedding` in node data | `GraphNode.data` contains 1536-float list; response is >1MB | Never put ORM objects directly in `data` dict; always build dict explicitly |
| Integer node IDs | React Flow edges fail to connect | All `id`, `source`, `target` must be prefixed strings: `f"concept-{c.id}"` |
| Missing "contains" edges | Concept nodes appear disconnected in graph | Synthesize `contains` edges in Python from `concept.course_id` FK; `edges` table has NO contains rows |
| `summary` returns `None` | `from_attributes` maps `concept.summary` (non-existent) not `concept.definition` | Always build `ConceptDetailResponse` explicitly: `summary=concept.definition` |
| Route order: `/{id}` before `/match` | `/courses/match` returns 422 (tries to cast "match" to int) | Keep `/match` registered BEFORE `/{course_id}` and `/{course_id}/graph` — existing file already correct |
| `AsyncSessionLocal()` in route | Second connection per request | Use `Depends(get_session)` — fix existing `/match` implementation |

---

## Metadata

**Analog search scope:** `backend/app/api/`, `backend/app/schemas/`, `backend/tests/`, `backend/app/core/`, `backend/app/models/`
**Files scanned:** 14 Python source files (all backend .py files)
**Key analogs used:**
- `backend/app/api/courses.py` — primary route pattern for both new routes
- `backend/app/schemas/courses.py` — primary schema pattern for both new schema files
- `backend/tests/test_courses.py` — primary test pattern for both new test files
- `backend/tests/test_ingest.py` — secondary test pattern (mock_session_factory fixture, router wiring test)
- `backend/app/core/database.py` — session dependency pattern
- `backend/app/api/router.py` — router registration pattern
**Pattern extraction date:** 2026-04-25
