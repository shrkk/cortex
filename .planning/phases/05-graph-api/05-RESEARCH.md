# Phase 5: Graph API — Research

**Researched:** 2026-04-25
**Domain:** FastAPI read endpoints, graph payload assembly, Pydantic v2 response schemas, pgvector cosine search
**Confidence:** HIGH (all findings verified directly against codebase; no new dependencies)

---

## Summary

Phase 5 is a pure API-surface phase: it adds new FastAPI read endpoints and refines/extends existing ones so the frontend can be built without rework. No new pipeline logic, no Alembic migrations, and no new Python packages are needed — everything required is already installed and in the DB schema from Phase 1–4.

The two most technically involved tasks are: (1) assembling the graph payload for `GET /courses/{id}/graph`, which requires a multi-table join that synthesizes a virtual course root node, collects concept nodes, collects flashcard child nodes, collects quiz nodes, and converts the DB-level edges table plus the implicit `concept.course_id` FK into typed edge objects; and (2) the `/courses/match` endpoint, which already exists and is largely correct but needs a minor correctness fix (it opens `AsyncSessionLocal` directly rather than using the injected `session` dependency — the existing implementation is inconsistent but functional).

All data needed for every endpoint is already stored in existing tables (`courses`, `concepts`, `concept_sources`, `flashcards`, `quizzes`, `edges`, `sources`). The `definition` field on `Concept` maps to the `summary` field in the GRAPH-04 response schema — this is the only field-name mismatch between DB and API.

**Primary recommendation:** Implement Phase 5 as four plans in two parallel waves — (Wave 1a) extend course endpoints + concept detail endpoint, (Wave 1b) the graph assembly endpoint — then (Wave 2) validate with curl tests and tests. Wave 1a and Wave 1b have no dependency on each other.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GRAPH-01 | GET /courses returns all courses for user | Already implemented in `courses.py` — verify response shape, add test |
| GRAPH-02 | POST /courses creates course, returns it with id | Already implemented in `courses.py` — verify response shape, add test |
| GRAPH-03 | GET /courses/{id}/graph returns all nodes and edges | New endpoint; multi-table assembly; virtual course root node; synthetic "contains" edges |
| GRAPH-04 | GET /concepts/{id} returns all detail fields: summary, key_points, gotchas, examples, student_questions, source_citations, flashcard_count, struggle_signals | New endpoint; "summary" maps to DB column `definition`; student_questions aggregated from concept_sources; source_citations from sources joined via concept_sources |
| GRAPH-05 | Node types: course (root), concept, flashcard, quiz | Enforced in GRAPH-03 node assembly logic |
| GRAPH-06 | Backend supports fast/cacheable graph polling every 5s | No backend state required; endpoint must be fast — avoid N+1 queries; use eager loading or explicit joins |
| GRAPH-07 | GET /courses/match?hint=[text] — embed hint, return best match or null | Already implemented; verify confidence threshold, null return, and test coverage |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Graph payload assembly | API / Backend | Database / Storage | Multi-table join in SQLAlchemy; DB does the joins, API shapes into nodes/edges |
| Virtual course root node synthesis | API / Backend | — | Course row from DB promoted to a `{type: "course", id: "course-{id}"}` node in Python; not stored in concepts |
| Synthetic "contains" edges | API / Backend | — | Derived from `concept.course_id` FK — no rows in `edges` table for contains (EDGE-01 design decision from Phase 3) |
| Concept detail aggregation | API / Backend | Database / Storage | Aggregate student_questions from concept_sources; source_citations from sources joined via concept_sources |
| pgvector hint embedding + cosine match | API / Backend (OpenAI call) | Database (HNSW index) | Hit OpenAI, then query pgvector HNSW index — existing pattern from `courses.py` |
| Polling readiness signal | Database / Storage | API / Backend | Frontend checks `sources.status` values; backend exposes per-course source statuses via graph endpoint or separate field |

---

## Standard Stack

### Core (all already in requirements.txt — no new installs)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastapi` | 0.136.1 | Router, dependency injection, response_model | Already running; all endpoints use it |
| `sqlalchemy` | 2.0.49 | Async ORM joins, selectinload, joinedload | Already in use; session-per-request via `get_session` |
| `pydantic` | 2.13.3 | Response schema validation; `model_config = {"from_attributes": True}` | All existing schemas use it |
| `openai` | 2.32.0 | text-embedding-3-small for /courses/match hint | Already used in courses.py and pipeline |

[VERIFIED: backend/requirements.txt]

### No New Dependencies
Phase 5 requires zero new pip installs. All needed packages are already declared and installed.

**Installation:** None needed.

---

## Architecture Patterns

### System Architecture Diagram

```
GET /courses/{id}/graph
  │
  ├─ SELECT courses WHERE id=:id AND user_id=1
  │    └─ Synthesize course root node: {id: "course-{id}", type: "course", ...}
  │
  ├─ SELECT concepts WHERE course_id=:id
  │    └─ Each concept → {id: "concept-{cid}", type: "concept", ...}
  │
  ├─ SELECT flashcards WHERE concept_id IN (concept_ids)
  │    └─ Each flashcard → {id: "flashcard-{fid}", type: "flashcard", ...}
  │
  ├─ SELECT quizzes WHERE course_id=:id (LIMIT 1 — most recent)
  │    └─ Each quiz → {id: "quiz-{qid}", type: "quiz", ...}
  │
  ├─ SELECT edges WHERE from_id IN (concept_ids) OR to_id IN (concept_ids)
  │    └─ Each edge → {id: "edge-{eid}", source: "concept-{from_id}", target: "concept-{to_id}", type: edge_type}
  │
  ├─ Synthesize "contains" edges: one edge per concept from course root
  │    └─ {source: "course-{id}", target: "concept-{cid}", type: "contains"}
  │
  ├─ Synthesize flashcard "contains" edges: one per flashcard → parent concept
  │    └─ {source: "concept-{cid}", target: "flashcard-{fid}", type: "contains"}
  │
  └─ Synthesize quiz "contains" edge: quiz → course root
       └─ {source: "course-{id}", target: "quiz-{qid}", type: "contains"}

GET /concepts/{id}
  │
  ├─ SELECT concepts WHERE id=:id
  ├─ SELECT concept_sources JOIN sources WHERE concept_id=:id
  │    ├─ Aggregate student_questions (from chat_log concept_sources)
  │    └─ Build source_citations: [{source_id, title, source_type, chunk_text?}]
  ├─ SELECT COUNT(*) FROM flashcards WHERE concept_id=:id
  └─ Return ConceptDetailResponse

GET /courses/match?hint=...
  │
  ├─ Embed hint with text-embedding-3-small
  ├─ pgvector cosine query on courses.embedding WHERE user_id=1
  └─ Return {course_id, title, confidence} OR null
```

### Recommended Project Structure

```
backend/app/
├── api/
│   ├── courses.py       # EXTEND: add GET /courses/{id}/graph
│   ├── concepts.py      # NEW: GET /concepts/{id}
│   ├── ingest.py        # Unchanged
│   ├── health.py        # Unchanged
│   └── router.py        # EXTEND: register concepts router
├── schemas/
│   ├── courses.py       # EXTEND: CourseResponse, GraphResponse, GraphNode, GraphEdge
│   ├── concepts.py      # NEW: ConceptDetailResponse, SourceCitation
│   └── ...
```

### Pattern 1: Graph Endpoint — Multi-Table Load Without N+1

The graph endpoint must not issue N+1 queries (one per concept to get its flashcards). Use a single IN-query for all flashcards and all edges belonging to the course's concepts.

```python
# Source: backend/app/api/courses.py existing query pattern + SQLAlchemy 2.0 docs
import sqlalchemy as sa
from app.models.models import Course, Concept, Flashcard, Quiz, Edge

@router.get("/{course_id}/graph", response_model=GraphResponse)
async def get_course_graph(course_id: int, session: AsyncSession = Depends(get_session)):
    # 1. Load course (validates ownership)
    course_result = await session.execute(
        sa.select(Course).where(Course.id == course_id, Course.user_id == 1)
    )
    course = course_result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    # 2. Load all concepts for this course
    concepts_result = await session.execute(
        sa.select(Concept).where(Concept.course_id == course_id)
    )
    concepts = concepts_result.scalars().all()
    concept_ids = [c.id for c in concepts]

    # 3. Load all flashcards for all concepts (single IN query — no N+1)
    flashcards_result = await session.execute(
        sa.select(Flashcard).where(Flashcard.concept_id.in_(concept_ids))
    )
    flashcards = flashcards_result.scalars().all()

    # 4. Load most recent quiz for the course
    quiz_result = await session.execute(
        sa.select(Quiz).where(Quiz.course_id == course_id)
        .order_by(Quiz.created_at.desc()).limit(1)
    )
    quiz = quiz_result.scalar_one_or_none()

    # 5. Load edges between concepts in this course
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

    # 6. Assemble payload (see Pattern 2)
    return _build_graph_payload(course, concepts, flashcards, quiz, edges)
```

[VERIFIED: backend/app/api/courses.py — `sa.select(Course).where(...)` pattern, HTTPException usage, `Depends(get_session)`]
[VERIFIED: backend/app/models/models.py — all model names and FK fields]

### Pattern 2: Graph Payload Assembly — Node and Edge Formats

Node IDs must be strings with a type prefix to avoid ID collisions across node types (course id=1 and concept id=1 would both be `1` without prefixes, breaking React Flow graph layout).

```python
# Source: [ASSUMED] — standard React Flow graph node format; required by @xyflow/react v12
# The frontend (@xyflow/react) expects {id: string, type: string, data: {...}}
# Edges: {id: string, source: string, target: string, type?: string}

def _build_graph_payload(course, concepts, flashcards, quiz, edges):
    nodes = []
    graph_edges = []

    # Course root node (virtual — synthesized from courses table row)
    course_node_id = f"course-{course.id}"
    nodes.append({
        "id": course_node_id,
        "type": "course",
        "data": {
            "label": course.title,
            "course_id": course.id,
            "description": course.description,
        }
    })

    # Concept nodes
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
                "flashcard_count": 0,  # populated below
                "struggle_signals": c.struggle_signals,
            }
        })
        # Synthetic course→concept "contains" edge
        graph_edges.append({
            "id": f"contains-{course.id}-{c.id}",
            "source": course_node_id,
            "target": concept_node_id,
            "type": "contains",
        })

    # Flashcard nodes + their concept→flashcard edges
    fc_by_concept: dict[int, int] = {}  # concept_id → count
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
            }
        })
        graph_edges.append({
            "id": f"contains-fc-{f.id}",
            "source": parent_node_id,
            "target": flashcard_node_id,
            "type": "contains",
        })
        fc_by_concept[f.concept_id] = fc_by_concept.get(f.concept_id, 0) + 1

    # Update flashcard_count on concept nodes
    for node in nodes:
        if node["type"] == "concept":
            cid = node["data"]["concept_id"]
            node["data"]["flashcard_count"] = fc_by_concept.get(cid, 0)

    # Quiz node + course→quiz edge (QUIZ-01: quiz hangs off course root)
    if quiz is not None:
        quiz_node_id = f"quiz-{quiz.id}"
        nodes.append({
            "id": quiz_node_id,
            "type": "quiz",
            "data": {
                "label": "Quiz",
                "quiz_id": quiz.id,
                "question_count": len(quiz.questions) if quiz.questions else 0,
            }
        })
        graph_edges.append({
            "id": f"contains-quiz-{quiz.id}",
            "source": course_node_id,
            "target": quiz_node_id,
            "type": "contains",
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

[VERIFIED: backend/app/models/models.py — all field names on Flashcard, Quiz, Edge, Concept, Course]
[ASSUMED] — node ID prefixing convention (`"course-{id}"`, `"concept-{id}"`) is the standard React Flow pattern for multi-type graphs; not formally specified in requirements but necessary to avoid ID collisions.

### Pattern 3: Concept Detail Endpoint (GRAPH-04)

The field name `summary` in the API response maps to `definition` in the DB (ORM model field: `Concept.definition`). All other fields are direct mappings.

```python
# Source: backend/app/models/models.py — Concept fields
# Source: backend/app/api/courses.py — existing route pattern

@router.get("/{concept_id}", response_model=ConceptDetailResponse)
async def get_concept_detail(concept_id: int, session: AsyncSession = Depends(get_session)):
    # Load concept
    result = await session.execute(
        sa.select(Concept).where(Concept.id == concept_id)
    )
    concept = result.scalar_one_or_none()
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    # Load concept_sources with their source rows (for student_questions + citations)
    cs_result = await session.execute(
        sa.select(ConceptSource, Source)
        .join(Source, ConceptSource.source_id == Source.id)
        .where(ConceptSource.concept_id == concept_id)
    )
    cs_rows = cs_result.all()

    # Aggregate student_questions from all chat_log ConceptSource rows
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

    # Flashcard count
    fc_result = await session.execute(
        sa.select(sa.func.count()).where(Flashcard.concept_id == concept_id)
    )
    flashcard_count = fc_result.scalar_one()

    return ConceptDetailResponse(
        id=concept.id,
        course_id=concept.course_id,
        title=concept.title,
        summary=concept.definition,        # <-- field rename: definition → summary
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

[VERIFIED: backend/app/models/models.py — ConceptSource.student_questions, Source.source_type, Concept.definition]
[VERIFIED: backend/app/models/models.py — Flashcard.concept_id FK]

### Pattern 4: /courses/match — Existing Implementation Review

`GET /courses/match` already exists in `backend/app/api/courses.py`. It is functionally correct. Minor issues to address in Phase 5:

1. It opens `AsyncSessionLocal()` directly inside the endpoint rather than using the injected `session` dependency. This creates an inconsistency (one more connection than needed) but is not incorrect. Fix for consistency.
2. It has no test coverage. Phase 5 must add tests.
3. Return type annotation `Optional[CourseMatchResponse]` is correct — returns null when confidence < 0.65 or no courses exist.

```python
# Current implementation is correct — verified in backend/app/api/courses.py lines 52–95
# The pgvector query uses: 1 - (embedding <=> CAST(:hint_vec AS vector)) AS confidence
# This is correct: pgvector <=> operator returns cosine distance; 1-distance = similarity
# CONFIDENCE_THRESHOLD = 0.65 is correct per GRAPH-07
```

[VERIFIED: backend/app/api/courses.py — lines 52–95, CONFIDENCE_THRESHOLD = 0.65]

### Pattern 5: Pydantic v2 Response Schema Style

All existing schemas use `model_config = {"from_attributes": True}` (Pydantic v2 ORM mode). New schemas must follow the same pattern.

```python
# Source: backend/app/schemas/courses.py — established pattern
from pydantic import BaseModel
from datetime import datetime
from typing import Any

class GraphNode(BaseModel):
    id: str            # prefixed string: "course-1", "concept-42", etc.
    type: str          # "course" | "concept" | "flashcard" | "quiz"
    data: dict[str, Any]

class GraphEdge(BaseModel):
    id: str
    source: str        # node id string
    target: str        # node id string
    type: str          # "contains" | "co_occurrence" | "prerequisite" | "related"
    data: dict[str, Any] = {}

class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]

class SourceCitation(BaseModel):
    source_id: int
    title: str | None
    source_type: str

class ConceptDetailResponse(BaseModel):
    id: int
    course_id: int
    title: str
    summary: str | None           # maps to Concept.definition
    key_points: list[str]
    gotchas: list[str]
    examples: list[str]
    student_questions: list[str]
    source_citations: list[SourceCitation]
    flashcard_count: int
    struggle_signals: dict | None
    depth: int | None

    model_config = {"from_attributes": True}
```

[VERIFIED: backend/app/schemas/courses.py — `model_config = {"from_attributes": True}` pattern]

### Anti-Patterns to Avoid

- **N+1 flashcard queries:** Never load flashcards inside a loop over concepts. Load all flashcards for the course's concept IDs in a single `WHERE concept_id IN (...)` query.
- **Returning embedding vectors in graph response:** `Concept.embedding` is a 1536-dimension list. Never include it in any API response — it will bloat responses to ~50KB per concept node.
- **Using `definition` as the API field name:** GRAPH-04 specifies `summary` as the field name. The Pydantic schema must map `Concept.definition` → `summary` in the response (use `Field(alias=...)` or explicit constructor mapping, not automatic `from_attributes` which would use `definition`).
- **Forgetting the virtual course root node:** The `edges` table has no rows for `contains` relationships (this was explicitly decided in Phase 3 — EDGE-01 is represented by `concept.course_id` FK, not edge rows). The graph endpoint must synthesize both the course root node and the `contains` edges in Python.
- **Using the wrong node ID format:** `concept.id` is an integer. React Flow node IDs must be strings. Use string prefixes: `f"concept-{c.id}"`, `f"course-{course.id}"`, etc.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cosine similarity search | Manual Python dot-product over all course rows | pgvector HNSW index via `<=>` operator | Already done in courses.py; O(log n) vs O(n) |
| Response serialization | Manual dict construction from ORM objects | Pydantic `response_model=` with `from_attributes=True` | FastAPI validates and serializes automatically |
| Embedding API call | Custom HTTP client | `AsyncOpenAI(api_key=...).embeddings.create(...)` | Already used in courses.py and pipeline.py |

---

## Tricky Parts

### Tricky Part 1: Field Name Mismatch — `definition` vs `summary`

GRAPH-04 requires a field named `summary`. The DB column and ORM attribute are named `definition`. Options:

**Option A (recommended):** Build the `ConceptDetailResponse` explicitly in the endpoint (not via `from_attributes` auto-mapping):
```python
return ConceptDetailResponse(
    ...
    summary=concept.definition,   # explicit rename at construction time
    ...
)
```

**Option B:** Use `Field(alias="definition")` in Pydantic schema and pass `by_alias=True` in serialization. More brittle and harder to read.

Use Option A. [ASSUMED] — this is the idiomatic Pydantic v2 approach for field renames between DB and API.

### Tricky Part 2: Assembling Graph from Multiple Tables Without N+1

With 20+ concept nodes and 3–6 flashcards per concept, a naive implementation issues 20+ SELECT queries. Use bulk IN queries (see Pattern 1). The graph endpoint should complete in < 100ms on local hardware for a demo-sized dataset.

### Tricky Part 3: Virtual Course Root Node

The `courses` table row is NOT a row in `concepts`. The graph endpoint must create a "virtual" node dict from `Course` ORM attributes. There is no `concept_id` for the course node — the ID is the string `f"course-{course.id}"`.

### Tricky Part 4: Quiz Node ID Collision

If the quiz is the most recent one and a new quiz is generated during the demo, the graph will include the new quiz ID. The frontend should handle this gracefully (it re-fetches every 5s while any source is processing). No special handling needed in the backend — just return the most recent quiz.

### Tricky Part 5: Polling Performance (GRAPH-06)

The frontend polls every 5s while any source is `pending` or `processing`. The graph endpoint must not be slow. Mitigations:
- Use explicit bulk IN queries (not lazy loading)
- Do NOT use `.selectinload()` ORM eager loading — it triggers additional queries per relationship; explicit IN queries are predictable
- No caching layer needed for demo scale (< 100 concept nodes)

### Tricky Part 6: Source Citations Format

GRAPH-04 requires `source_citations`. The spec doesn't define the exact shape but the frontend (UI-05) shows "source citations with chunk text". For Phase 5, return `[{source_id, title, source_type}]` without chunk text — chunk text retrieval adds complexity and the REQUIREMENTS.md UI-05 says "chunk text accessible via citations in detail panel only." The exact chunk text retrieval can be added in Phase 6 if needed.

---

## Common Pitfalls

### Pitfall 1: Embedding Vectors in API Response
**What goes wrong:** `GraphNode.data` accidentally includes `concept.embedding` (a 1536-float list), making each concept node ~50KB. The graph response for 20 concepts becomes 1MB+ and crashes React Flow.
**Why it happens:** Pydantic `from_attributes=True` includes all model attributes unless explicitly excluded.
**How to avoid:** Never put ORM objects directly into `GraphNode.data`. Always build the `data` dict explicitly, naming only the fields needed.
**Warning signs:** Graph response JSON is unexpectedly large; browser tab hangs on graph load.

### Pitfall 2: Integer vs String Node IDs
**What goes wrong:** React Flow receives `id: 42` (integer) instead of `id: "concept-42"` (string). The library accepts both but edges fail to connect because `source: "concept-42"` doesn't match node `id: 42`.
**Why it happens:** Forgetting to prefix integer PKs when assembling nodes.
**How to avoid:** All node IDs must be strings: `f"concept-{c.id}"`, `f"course-{course.id}"`. All edge `source`/`target` must use the same prefixed strings.
**Warning signs:** Graph renders nodes but no edges connect; React Flow console warnings about missing nodes.

### Pitfall 3: Missing "contains" Edges (Virtual Edges Not Synthesized)
**What goes wrong:** The graph returns concept nodes but no edges connecting them to the course root, so React Flow renders all nodes as isolated (no dagre layout can be applied).
**Why it happens:** `edges` table has no `contains` rows (EDGE-01 design decision). If the endpoint only queries the `edges` table, it gets zero "contains" edges.
**How to avoid:** After assembling concept nodes, loop over concepts and synthesize `{source: "course-{id}", target: "concept-{cid}", type: "contains"}` edges in Python — no DB query needed.
**Warning signs:** Graph endpoint returns edges only of type `co_occurrence`/`prerequisite`; course node appears disconnected.

### Pitfall 4: `summary` Field Not Mapped Correctly
**What goes wrong:** `GET /concepts/{id}` returns `{"summary": null}` even though `concept.definition` is populated.
**Why it happens:** Pydantic `from_attributes=True` maps attribute `definition` to field `definition`, not `summary`. If the schema has a field named `summary` and auto-maps from the ORM object, it maps to `concept.summary` (which doesn't exist) → `None`.
**How to avoid:** Build `ConceptDetailResponse` explicitly: `ConceptDetailResponse(summary=concept.definition, ...)`.
**Warning signs:** `GET /concepts/{id}` always returns `"summary": null`; concept detail panel shows blank description.

### Pitfall 5: Router Registration Order in courses.py
**What goes wrong:** `GET /courses/match` returns a 404 or routes to `GET /courses/{id}` with `id="match"` (SQLAlchemy raises a cast error converting "match" to integer).
**Why it happens:** FastAPI routes are matched in registration order. `GET /courses/{course_id}` registered BEFORE `GET /courses/match` will catch `/courses/match` first, treating "match" as a course_id integer.
**How to avoid:** Register `/courses/match` BEFORE `/courses/{course_id}` in the router. [VERIFIED: existing courses.py — `/match` is registered before any `/{id}` routes — this is already correct and must be preserved when adding `/{id}/graph`.]
**Warning signs:** `GET /courses/match?hint=test` returns 422 Unprocessable Entity ("value is not a valid integer").

---

## Pydantic Response Schemas — Exact Field Names

### Existing schemas (already in `backend/app/schemas/courses.py`)

```python
class CourseCreate(BaseModel):
    title: str
    user_id: int = 1

class CourseResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: str | None = None
    created_at: datetime
    model_config = {"from_attributes": True}

class CourseMatchResponse(BaseModel):
    course_id: int
    title: str
    confidence: float
```

### New schemas to create

**`backend/app/schemas/graph.py`** (new file):

```python
from pydantic import BaseModel
from typing import Any

class GraphNode(BaseModel):
    id: str                      # "course-1" | "concept-42" | "flashcard-7" | "quiz-3"
    type: str                    # "course" | "concept" | "flashcard" | "quiz"
    data: dict[str, Any]         # type-specific payload (no embedding vectors)

class GraphEdge(BaseModel):
    id: str                      # "contains-1-42" | "edge-{edge_table_id}"
    source: str                  # prefixed node id
    target: str                  # prefixed node id
    type: str                    # "contains" | "co_occurrence" | "prerequisite" | "related"
    data: dict[str, Any] = {}    # optional: {"weight": 1.5}

class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
```

**`backend/app/schemas/concepts.py`** (new file):

```python
from pydantic import BaseModel
from typing import Any

class SourceCitation(BaseModel):
    source_id: int
    title: str | None = None
    source_type: str             # "pdf" | "url" | "image" | "text" | "chat_log"

class ConceptDetailResponse(BaseModel):
    id: int
    course_id: int
    title: str
    summary: str | None = None        # maps to Concept.definition — renamed in response
    key_points: list[str] = []
    gotchas: list[str] = []
    examples: list[str] = []
    student_questions: list[str] = [] # aggregated from ConceptSource.student_questions (chat_log only)
    source_citations: list[SourceCitation] = []
    flashcard_count: int = 0
    struggle_signals: dict | None = None
    depth: int | None = None
```

Note: `ConceptDetailResponse` does NOT use `from_attributes=True` because it is built explicitly in the endpoint (field renaming `definition` → `summary` requires explicit construction).

---

## Wave Dependencies

### Wave 0 (TDD RED — test scaffolding)
- Create test stubs with failing assertions for all 7 GRAPH requirements
- Create skeleton module files (`concepts.py` API and schema)

### Wave 1a (parallel — no inter-dependency with 1b)
- Extend `courses.py`: ensure GET /courses and POST /courses are tested
- Add `GET /courses/match` test coverage (already implemented, add tests)
- Create `concepts.py` API router with `GET /concepts/{id}` implementation

### Wave 1b (parallel — no inter-dependency with 1a)
- Add `GET /courses/{id}/graph` to `courses.py`
- Create graph schemas in `schemas/graph.py`

### Wave 2 (blocked on Wave 1a + 1b)
- Integration verification: curl tests for all endpoints
- Register `concepts` router in `router.py`
- Full test suite

Wave 1a and Wave 1b have no shared files (1a: `concepts.py` + `schemas/concepts.py`; 1b: `courses.py` graph endpoint + `schemas/graph.py`).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 0.24.0 |
| Config file | `backend/pytest.ini` (`asyncio_mode = auto`, `testpaths = tests`) |
| Quick run command | `pytest tests/test_graph_api.py tests/test_concept_detail.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GRAPH-01 | GET /courses returns list | integration | `pytest tests/test_graph_api.py::test_list_courses -x` | ❌ Wave 0 |
| GRAPH-02 | POST /courses returns course with id | integration | `pytest tests/test_graph_api.py::test_create_course -x` | ❌ Wave 0 |
| GRAPH-03 | GET /courses/{id}/graph returns nodes+edges | integration | `pytest tests/test_graph_api.py::test_graph_nodes_and_edges -x` | ❌ Wave 0 |
| GRAPH-04 | GET /concepts/{id} all detail fields | integration | `pytest tests/test_concept_detail.py::test_concept_detail_fields -x` | ❌ Wave 0 |
| GRAPH-05 | Node types: course, concept, flashcard, quiz | integration | `pytest tests/test_graph_api.py::test_graph_node_types -x` | ❌ Wave 0 |
| GRAPH-06 | Graph endpoint is fast; no N+1 | unit/structural | `pytest tests/test_graph_api.py::test_no_n_plus_one_queries -x` | ❌ Wave 0 |
| GRAPH-07 | GET /courses/match returns match or null | integration | `pytest tests/test_graph_api.py::test_course_match_returns_null -x` | ❌ Wave 0 |

### Mocking Strategy

Tests use `httpx.AsyncClient` with `ASGITransport` (already established in `conftest.py`). For GRAPH-07, mock the OpenAI client because the test environment may not have an API key.

```python
# Source: backend/tests/conftest.py — existing client fixture
from unittest.mock import AsyncMock, MagicMock, patch

async def test_course_match_no_courses(client):
    """GRAPH-07 — returns null when no courses with embeddings exist."""
    with patch("app.api.courses.AsyncOpenAI") as mock_openai_cls:
        mock_openai = AsyncMock()
        mock_openai.embeddings.create = AsyncMock(return_value=_make_embed_response([0.1]*1536))
        mock_openai_cls.return_value = mock_openai
        response = await client.get("/courses/match?hint=backpropagation")
    assert response.status_code == 200
    assert response.json() is None
```

### curl Verification Commands (Phase Gate)

```bash
# GRAPH-01: list courses
curl -s http://localhost:8000/courses | jq 'length'

# GRAPH-02: create course
curl -s -X POST http://localhost:8000/courses \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Course", "user_id": 1}' | jq '.id'

# GRAPH-03: graph endpoint (requires a course with data)
curl -s "http://localhost:8000/courses/1/graph" | jq '{
  node_count: (.nodes | length),
  edge_count: (.edges | length),
  node_types: ([.nodes[].type] | unique),
  edge_types: ([.edges[].type] | unique)
}'

# GRAPH-04: concept detail
curl -s "http://localhost:8000/concepts/1" | jq 'keys'
# Expected keys include: id, course_id, title, summary, key_points, gotchas,
# examples, student_questions, source_citations, flashcard_count, struggle_signals

# GRAPH-07: course match
curl -s "http://localhost:8000/courses/match?hint=backpropagation" | jq .
# Returns {course_id, title, confidence} or null

curl -s "http://localhost:8000/courses/match?hint=zzzznonexistent" | jq .
# Returns null
```

### Sampling Rate
- **Per task commit:** `pytest tests/test_graph_api.py tests/test_concept_detail.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green + all curl commands above pass manually

### Wave 0 Gaps
- [ ] `tests/test_graph_api.py` — covers GRAPH-01, GRAPH-02, GRAPH-03, GRAPH-05, GRAPH-06, GRAPH-07
- [ ] `tests/test_concept_detail.py` — covers GRAPH-04
- [ ] `backend/app/api/concepts.py` — skeleton (importable, GET /concepts/{id} stub returning 501)
- [ ] `backend/app/schemas/graph.py` — GraphNode, GraphEdge, GraphResponse
- [ ] `backend/app/schemas/concepts.py` — ConceptDetailResponse, SourceCitation

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | user_id=1 hardcoded — no auth in v1 |
| V3 Session Management | no | No web sessions |
| V4 Access Control | partial | All endpoints hardcode `WHERE user_id=1`; course_id validation needed to prevent ID enumeration |
| V5 Input Validation | yes | `hint` param on /courses/match: truncate before embedding (max 500 chars); `course_id` is int — FastAPI validates type |
| V6 Cryptography | no | No cryptographic operations in Phase 5 |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Course ID enumeration | Information Disclosure | All course/concept queries include `WHERE user_id=1` check — `GET /courses/{id}/graph` must 404 for courses belonging to other users (currently single-user, but the check prevents future issues) |
| Hint injection via /courses/match | Tampering | Hint is embedded via OpenAI API, not executed as code or SQL — no injection risk; truncate to 500 chars to limit embedding cost |
| Large hint causing slow embed call | Denial of Service | Truncate `hint` to `hint[:500]` before calling OpenAI — enforced in endpoint |
| Concept ID enumeration | Information Disclosure | `GET /concepts/{id}` should validate that the concept belongs to a course owned by user_id=1; add `JOIN courses WHERE courses.user_id=1` |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Node IDs use string prefixes ("course-1", "concept-42") to avoid cross-type collisions | Pattern 2 | If the frontend expects integer IDs, all edge source/target references will break; must verify with frontend consumer before finalizing |
| A2 | Only the most recent quiz (ORDER BY created_at DESC LIMIT 1) is included in the graph | Pattern 1 | If multiple quizzes should appear, this assumption is wrong; requirements say "quiz nodes" (plural in GRAPH-05) but QUIZ-01 says quiz is a "standalone node" — implies one at a time |
| A3 | `source_citations` in GRAPH-04 does not include raw chunk text (just source metadata) | Tricky Part 6 | UI-05 says "source citations with chunk text" — if the frontend needs chunk text in Phase 5, this assumption is wrong and the join needs to extend to the `chunks` table |
| A4 | `definition` → `summary` rename is done at construction time (not via Pydantic alias) | Tricky Part 1 | No functional risk — both approaches produce the same JSON output; alias approach is more fragile |

---

## Open Questions (RESOLVED)

1. **Multiple quizzes per course**
   - What we know: Each `POST /quiz` creates a new row in `quizzes`. A course can have multiple quiz rows over time.
   - What's unclear: Should `GET /courses/{id}/graph` return ONE quiz node (most recent) or ALL quiz nodes?
   - Recommendation: Return only the most recent quiz to keep the graph uncluttered. If the demo needs multiple quizzes shown, revisit in Phase 7.
   - RESOLVED: Return only the most recent quiz node per course (ORDER BY created_at DESC LIMIT 1). Keeps graph uncluttered; revisit in Phase 7 if needed.

2. **Flashcard nodes visible in graph at demo scale**
   - What we know: Each concept gets 3–6 flashcards = potentially 60–120 flashcard nodes for 20 concepts.
   - What's unclear: Does the frontend actually render flashcard nodes as graph nodes (React Flow), or does the graph response just include them for the frontend to decide?
   - Recommendation: Include them in the response as specified (GRAPH-03, GRAPH-05). The frontend can choose to hide them by default and show on click (UI-02/UI-05 detail). No backend change needed.
   - RESOLVED: Include all flashcard nodes in the response (GRAPH-03, GRAPH-05 require it). Frontend decides rendering behaviour in Phase 6.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| PostgreSQL + pgvector | All graph queries | ✓ | pgvector:pg16, running | — |
| Python 3 | Backend | ✓ | 3.14.3 | — |
| `openai` SDK | /courses/match | ✓ | 2.32.0 pinned | Skip match (return null) if no API key |
| `OPENAI_API_KEY` | /courses/match embedding | ✓ (set in .env) | — | Tests mock it; endpoint returns null if key absent |

[VERIFIED: backend/requirements.txt — openai==2.32.0]
[VERIFIED: backend/app/api/courses.py — `if not settings.openai_api_key: return None` guard already present]

---

## Sources

### Primary (HIGH confidence)
- `backend/app/models/models.py` — all ORM model field names, FK relationships, JSON field types confirmed
- `backend/alembic/versions/0001_initial.py` — confirmed schema: edges table has `from_id`/`to_id` as concept FKs only; no "contains" rows; concepts has `definition` (not `summary`)
- `backend/alembic/versions/0002_course_embeddings.py` — confirmed `courses.embedding` Vector(1536) added
- `backend/app/api/courses.py` — existing GET /courses, POST /courses, GET /courses/match implementations; confirmed route registration order (match before {id})
- `backend/app/schemas/courses.py` — CourseResponse, CourseMatchResponse, CourseCreate confirmed
- `backend/app/core/database.py` — AsyncSessionLocal, get_session dependency confirmed; `expire_on_commit=False`
- `backend/app/main.py` — CORS config, lifespan hook, router registration confirmed
- `backend/tests/conftest.py` — `client` fixture (AsyncClient + ASGITransport) confirmed
- `backend/pytest.ini` — `asyncio_mode = auto`, `testpaths = tests` confirmed
- `.planning/phases/03-extraction-resolution-edges/03-RESEARCH.md` — EDGE-01 design decision: "contains" edges represented by `concept.course_id` FK, NOT in `edges` table
- `.planning/phases/04-flashcards-struggle-quiz/04-CONTEXT.md` — confirmed quiz is attached to course root (QUIZ-01); no SRS fields on flashcards

### Secondary (MEDIUM confidence)
- `backend/requirements.txt` — all package versions pinned; no new packages needed for Phase 5

### Tertiary (LOW confidence)
- Node ID string prefix convention (`"course-{id}"`) — [ASSUMED] based on React Flow standard practice

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all existing, pinned versions verified
- Architecture/patterns: HIGH — all endpoints derived from existing code patterns; all schema fields verified against DB migration
- Graph payload assembly: HIGH — all model fields verified; contains-edge synthesis derived from confirmed Phase 3 design decision
- Field rename (definition→summary): HIGH — DB field verified as `definition`; API spec says `summary`; mapping strategy clear
- Node ID format: MEDIUM — prefixed string IDs are standard practice but [ASSUMED]; not formally specified in requirements
- Pitfalls: HIGH — derived from actual codebase constraints (route ordering, N+1, embedding vectors)

**Research date:** 2026-04-25
**Valid until:** 2026-05-25 (stable APIs; all packages pinned)
