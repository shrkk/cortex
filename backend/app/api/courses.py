from __future__ import annotations

from typing import Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from openai import AsyncOpenAI, APIError as OpenAIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, get_session
from app.models.models import Course, Concept, Flashcard, Quiz, Edge
from app.schemas.courses import CourseCreate, CourseMatchResponse, CourseResponse
from app.schemas.graph import GraphResponse

router = APIRouter()

# ---------------------------------------------------------------------------
# GET /courses — list all courses for user_id=1
# ---------------------------------------------------------------------------

@router.get("", response_model=list[CourseResponse])
async def list_courses(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        sa.select(Course).where(Course.user_id == 1).order_by(Course.created_at)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# POST /courses — create a new course
# ---------------------------------------------------------------------------

@router.post("", response_model=CourseResponse, status_code=201)
async def create_course(
    body: CourseCreate,
    session: AsyncSession = Depends(get_session),
):
    course = Course(title=body.title, user_id=body.user_id)
    session.add(course)
    await session.commit()
    await session.refresh(course)
    return course


# ---------------------------------------------------------------------------
# GET /courses/match — cosine similarity pre-flight for Swift notch
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLD = 0.65


@router.get("/match", response_model=Optional[CourseMatchResponse])
async def match_course(hint: str, session: AsyncSession = Depends(get_session)):
    """Embed hint and find best-matching course.

    Returns {course_id, title, confidence} if best confidence >= 0.65.
    Returns null if no courses exist, no course has an embedding, or best < 0.65.
    Contract: null means "user must choose" (D-07).
    """
    hint = hint[:500]

    if not settings.openai_api_key:
        return None

    # Embed the hint text
    try:
        openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        embed_response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=hint,
        )
        hint_vector = embed_response.data[0].embedding
    except OpenAIError:
        return None

    # Cosine similarity query via pgvector operator <=>
    # 1 - (embedding <=> hint_vec) = cosine similarity (pgvector returns cosine distance)
    result = await session.execute(
        sa.text(
            """
            SELECT id, title, 1 - (embedding <=> CAST(:hint_vec AS vector)) AS confidence
            FROM courses
            WHERE user_id = 1 AND embedding IS NOT NULL
            ORDER BY confidence DESC
            LIMIT 1
            """
        ),
        {"hint_vec": str(hint_vector)},
    )
    row = result.fetchone()

    if row is None or row.confidence < CONFIDENCE_THRESHOLD:
        return None

    return CourseMatchResponse(
        course_id=row.id,
        title=row.title,
        confidence=float(row.confidence),
    )


# ---------------------------------------------------------------------------
# GET /courses/{course_id}/graph — assemble full graph payload
# ---------------------------------------------------------------------------

@router.get("/{course_id}/graph", response_model=GraphResponse)
async def get_course_graph(
    course_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Assemble course graph: course root node, concept nodes, flashcard nodes,
    quiz node, all edges. Contains edges are synthesized in Python from
    concept.course_id FK — the edges table has NO contains rows (EDGE-01).
    """
    # 1. Load course (validates ownership via user_id=1 guard)
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

    # 3. Load all flashcards in one IN query — no N+1 (GRAPH-06)
    if concept_ids:
        flashcards_result = await session.execute(
            sa.select(Flashcard).where(Flashcard.concept_id.in_(concept_ids))
        )
        flashcards = flashcards_result.scalars().all()
    else:
        flashcards = []

    # 4. Most recent quiz for the course (QUIZ-01: quiz hangs off course root)
    quiz_result = await session.execute(
        sa.select(Quiz).where(Quiz.course_id == course_id)
        .order_by(Quiz.created_at.desc()).limit(1)
    )
    quiz = quiz_result.scalar_one_or_none()

    # 5. Edges between concepts (co_occurrence, prerequisite, related) — single IN query
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

    return _build_graph_payload(course, concepts, flashcards, quiz, edges)


def _build_graph_payload(course, concepts, flashcards, quiz, edges) -> dict:
    """Assemble GraphResponse dict from ORM objects.

    Rules:
    - Course root node is virtual: synthesized from courses table row (no concept row for it).
    - "contains" edges are synthetic: derived from concept.course_id FK and flashcard.concept_id FK.
      The edges table has NO contains rows (Phase 3 EDGE-01 design decision).
    - All node IDs are prefixed strings to avoid cross-type React Flow ID collisions.
    - Embedding vectors are NEVER included in node data (50KB bloat per concept node).
    """
    nodes: list[dict] = []
    graph_edges: list[dict] = []

    course_node_id = f"course-{course.id}"

    # Course root node (virtual — not a row in concepts table)
    nodes.append({
        "id": course_node_id,
        "type": "course",
        "data": {
            "label": course.title,
            "course_id": course.id,
            "description": course.description,
        },
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
                "flashcard_count": 0,  # backfilled after flashcard pass below
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

    # Backfill flashcard_count on concept nodes
    for node in nodes:
        if node["type"] == "concept":
            cid = node["data"]["concept_id"]
            node["data"]["flashcard_count"] = fc_count_by_concept.get(cid, 0)

    # Quiz node + synthetic course→quiz "contains" edge (QUIZ-01)
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
