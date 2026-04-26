"""
Tests for graph API endpoints: GRAPH-01–03, GRAPH-05–07.
Wave 0 — RED state. All tests fail until Wave 1 implementations are complete.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.database import get_session


async def test_list_courses_returns_list(client):
    """GRAPH-01 — GET /courses returns HTTP 200 and a list."""
    from app.main import app
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(
        return_value=MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        )
    )

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        response = await client.get("/courses")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_create_course_returns_id(client):
    """GRAPH-02 — POST /courses returns HTTP 201 with 'id' field."""
    from app.main import app

    mock_session = AsyncMock()

    async def mock_refresh(obj):
        obj.id = 7
        obj.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    mock_session.commit = AsyncMock()
    mock_session.refresh = mock_refresh
    mock_session.add = MagicMock()

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        response = await client.post(
            "/courses",
            json={"title": "CS 229: Machine Learning"},
        )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data


async def test_graph_returns_nodes_and_edges(client):
    """GRAPH-03 — GET /courses/1/graph returns HTTP 200 with 'nodes' and 'edges' keys.

    RED state: Returns 404 (route not registered) until Wave 1b implements the endpoint.
    """
    from app.main import app
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_course = MagicMock()
    mock_course.id = 1
    mock_course.user_id = 1
    mock_course.title = "CS229"
    mock_course.description = None

    mock_concept = MagicMock()
    mock_concept.id = 10
    mock_concept.course_id = 1
    mock_concept.title = "Gradient Descent"
    mock_concept.depth = 1
    mock_concept.struggle_signals = None
    mock_concept.definition = "optimization algo"
    mock_concept.key_points = []
    mock_concept.gotchas = []
    mock_concept.examples = []

    mock_session = AsyncMock(spec=AsyncSession)
    responses = [
        # call 0: SELECT course
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_course)),
        # call 1: SELECT concepts
        MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(all=MagicMock(return_value=[mock_concept]))
            )
        ),
        # call 2: SELECT flashcards WHERE concept_id IN (...)
        MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ),
        # call 3: SELECT quiz
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        # call 4: SELECT edges
        MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ),
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


async def test_graph_node_types_include_course_and_concept(client):
    """GRAPH-05 — Node type strings include 'course' and 'concept' in returned node list.

    RED state: Returns 404 until Wave 1b implements the graph endpoint.
    """
    from app.main import app
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_course = MagicMock()
    mock_course.id = 1
    mock_course.user_id = 1
    mock_course.title = "CS229"
    mock_course.description = None

    mock_concept = MagicMock()
    mock_concept.id = 10
    mock_concept.course_id = 1
    mock_concept.title = "Gradient Descent"
    mock_concept.depth = 1
    mock_concept.struggle_signals = None
    mock_concept.definition = "optimization algo"
    mock_concept.key_points = []
    mock_concept.gotchas = []
    mock_concept.examples = []

    mock_session = AsyncMock(spec=AsyncSession)
    responses = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_course)),
        MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(all=MagicMock(return_value=[mock_concept]))
            )
        ),
        MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ),
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ),
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
    node_types = {n["type"] for n in data["nodes"]}
    assert "course" in node_types
    assert "concept" in node_types


async def test_graph_has_contains_edge(client):
    """GRAPH-05 + GRAPH-03 — Edges list contains at least one edge with type 'contains'.

    RED state: Returns 404 until Wave 1b implements the graph endpoint.
    """
    from app.main import app
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_course = MagicMock()
    mock_course.id = 1
    mock_course.user_id = 1
    mock_course.title = "CS229"
    mock_course.description = None

    mock_concept = MagicMock()
    mock_concept.id = 10
    mock_concept.course_id = 1
    mock_concept.title = "Gradient Descent"
    mock_concept.depth = 1
    mock_concept.struggle_signals = None
    mock_concept.definition = "optimization algo"
    mock_concept.key_points = []
    mock_concept.gotchas = []
    mock_concept.examples = []

    mock_session = AsyncMock(spec=AsyncSession)
    responses = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_course)),
        MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(all=MagicMock(return_value=[mock_concept]))
            )
        ),
        MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ),
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ),
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
    edge_types = [e["type"] for e in data["edges"]]
    assert "contains" in edge_types


async def test_graph_node_ids_are_prefixed_strings(client):
    """GRAPH-05 — Every node 'id' is a string starting with a type prefix.

    RED state: Returns 404 until Wave 1b implements the graph endpoint.
    """
    from app.main import app
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_course = MagicMock()
    mock_course.id = 1
    mock_course.user_id = 1
    mock_course.title = "CS229"
    mock_course.description = None

    mock_concept = MagicMock()
    mock_concept.id = 10
    mock_concept.course_id = 1
    mock_concept.title = "Gradient Descent"
    mock_concept.depth = 1
    mock_concept.struggle_signals = None
    mock_concept.definition = "optimization algo"
    mock_concept.key_points = []
    mock_concept.gotchas = []
    mock_concept.examples = []

    mock_session = AsyncMock(spec=AsyncSession)
    responses = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_course)),
        MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(all=MagicMock(return_value=[mock_concept]))
            )
        ),
        MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ),
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ),
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
    valid_prefixes = ("course-", "concept-", "flashcard-", "quiz-")
    for node in data["nodes"]:
        assert isinstance(node["id"], str)
        assert node["id"].startswith(valid_prefixes), (
            f"Node id '{node['id']}' does not start with a valid prefix"
        )


async def test_graph_endpoint_no_n_plus_one_structural(client):
    """GRAPH-06 structural guard — verify endpoint makes exactly 5 session.execute calls
    for a course with 1 concept.

    RED state: Returns 404 (route not registered) → execute count is 0, assertion fails.
    """
    from app.main import app
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_course = MagicMock()
    mock_course.id = 1
    mock_course.user_id = 1
    mock_course.title = "CS229"
    mock_course.description = None

    mock_concept = MagicMock()
    mock_concept.id = 10
    mock_concept.course_id = 1
    mock_concept.title = "Gradient Descent"
    mock_concept.depth = 1
    mock_concept.struggle_signals = None
    mock_concept.definition = "optimization algo"
    mock_concept.key_points = []
    mock_concept.gotchas = []
    mock_concept.examples = []

    mock_session = AsyncMock(spec=AsyncSession)
    responses = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_course)),
        MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(all=MagicMock(return_value=[mock_concept]))
            )
        ),
        MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ),
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        MagicMock(
            scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        ),
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
    # Exactly 5 DB queries: course, concepts, flashcards, quiz, edges
    assert mock_session.execute.call_count == 5


async def test_course_match_returns_null_below_threshold(client):
    """GRAPH-07 — GET /courses/match?hint=test returns null when confidence=0.64."""
    from app.main import app
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_embed_response = MagicMock()
    mock_embed_response.data = [MagicMock(embedding=[0.1] * 1536)]

    mock_row = MagicMock()
    mock_row.confidence = 0.64  # below threshold

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with patch("app.api.courses.settings") as mock_settings, \
             patch("app.api.courses.AsyncOpenAI") as mock_openai_cls:

            mock_settings.openai_api_key = "sk-test"

            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_embed_response)
            mock_openai_cls.return_value = mock_client

            response = await client.get("/courses/match?hint=test")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    assert response.json() is None


async def test_course_match_returns_match_at_threshold(client):
    """GRAPH-07 — GET /courses/match?hint=test returns {course_id, title, confidence}
    when confidence=0.65."""
    from app.main import app
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_embed_response = MagicMock()
    mock_embed_response.data = [MagicMock(embedding=[0.1] * 1536)]

    mock_row = MagicMock()
    mock_row.confidence = 0.65  # at threshold — should return
    mock_row.id = 3
    mock_row.title = "CS 101"

    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.fetchone.return_value = mock_row
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        with patch("app.api.courses.settings") as mock_settings, \
             patch("app.api.courses.AsyncOpenAI") as mock_openai_cls:

            mock_settings.openai_api_key = "sk-test"

            mock_client = AsyncMock()
            mock_client.embeddings.create = AsyncMock(return_value=mock_embed_response)
            mock_openai_cls.return_value = mock_client

            response = await client.get("/courses/match?hint=test")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert data["course_id"] == 3
    assert data["title"] == "CS 101"
    assert data["confidence"] == 0.65


async def test_course_match_hint_truncated_to_500_chars(client):
    """GRAPH-07 DoS mitigation — hint longer than 500 chars is accepted without error.

    This test currently PASSES (FastAPI doesn't reject long strings); the truncation
    implementation guard is needed in Wave 1.
    """
    long_hint = "a" * 600

    with patch("app.api.courses.settings") as mock_settings:
        mock_settings.openai_api_key = None  # short-circuit before OpenAI call
        response = await client.get(f"/courses/match?hint={long_hint}")

    # Must not return 422 (validation error) — long strings are accepted
    assert response.status_code == 200
