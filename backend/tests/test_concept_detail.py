"""
Tests for concept detail endpoint: GET /concepts/{id}.

Wave 0 — RED state. All tests call GET /concepts/{id} which returns 501 (stub).
Tests that check status_code == 200 will FAIL — confirming RED state.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.database import get_session


async def test_concept_detail_returns_200(client):
    """GRAPH-04 — GET /concepts/5 returns HTTP 200.

    RED state: concept endpoint returns 501 stub → this test FAILS.
    """
    from app.main import app
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_concept = MagicMock()
    mock_concept.id = 5
    mock_concept.course_id = 1
    mock_concept.title = "Gradient Descent"
    mock_concept.definition = "An iterative optimization algorithm"
    mock_concept.key_points = ["converges"]
    mock_concept.gotchas = ["lr sensitivity"]
    mock_concept.examples = ["linreg"]
    mock_concept.struggle_signals = None
    mock_concept.depth = 2

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(side_effect=[
        # call 0: concept lookup
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_concept)),
        # call 1: ownership check
        MagicMock(scalar_one_or_none=MagicMock(return_value=1)),
        # call 2: concept_sources join
        MagicMock(all=MagicMock(return_value=[])),
        # call 3: flashcard count
        MagicMock(scalar_one=MagicMock(return_value=3)),
    ])

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        response = await client.get("/concepts/5")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 200


async def test_concept_detail_has_all_required_fields(client):
    """GRAPH-04 — response JSON contains all required fields.

    RED state: concept endpoint returns 501 stub → this test FAILS.
    """
    from app.main import app
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_concept = MagicMock()
    mock_concept.id = 5
    mock_concept.course_id = 1
    mock_concept.title = "Gradient Descent"
    mock_concept.definition = "An iterative optimization algorithm"
    mock_concept.key_points = ["converges"]
    mock_concept.gotchas = ["lr sensitivity"]
    mock_concept.examples = ["linreg"]
    mock_concept.struggle_signals = None
    mock_concept.depth = 2

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_concept)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=1)),
        MagicMock(all=MagicMock(return_value=[])),
        MagicMock(scalar_one=MagicMock(return_value=3)),
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
    required_fields = {
        "id", "course_id", "title", "summary", "key_points", "gotchas",
        "examples", "student_questions", "source_citations", "flashcard_count",
        "struggle_signals",
    }
    assert required_fields.issubset(data.keys())


async def test_concept_detail_summary_maps_from_definition(client):
    """GRAPH-04 critical rename — response['summary'] equals the value set on
    concept.definition (NOT null).

    RED state: concept endpoint returns 501 stub → this test FAILS.
    """
    from app.main import app
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_concept = MagicMock()
    mock_concept.id = 5
    mock_concept.course_id = 1
    mock_concept.title = "Gradient Descent"
    mock_concept.definition = "An iterative optimization algorithm"
    mock_concept.key_points = ["converges"]
    mock_concept.gotchas = ["lr sensitivity"]
    mock_concept.examples = ["linreg"]
    mock_concept.struggle_signals = None
    mock_concept.depth = 2

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_concept)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=1)),
        MagicMock(all=MagicMock(return_value=[])),
        MagicMock(scalar_one=MagicMock(return_value=3)),
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
    assert data["summary"] == "An iterative optimization algorithm"


async def test_concept_detail_definition_not_in_response(client):
    """GRAPH-04 rename guard — 'definition' key is NOT present in response JSON.

    RED state: concept endpoint returns 501 stub → this test FAILS.
    """
    from app.main import app
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_concept = MagicMock()
    mock_concept.id = 5
    mock_concept.course_id = 1
    mock_concept.title = "Gradient Descent"
    mock_concept.definition = "An iterative optimization algorithm"
    mock_concept.key_points = ["converges"]
    mock_concept.gotchas = ["lr sensitivity"]
    mock_concept.examples = ["linreg"]
    mock_concept.struggle_signals = None
    mock_concept.depth = 2

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(side_effect=[
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_concept)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=1)),
        MagicMock(all=MagicMock(return_value=[])),
        MagicMock(scalar_one=MagicMock(return_value=3)),
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
    assert "definition" not in data


async def test_concept_detail_404_for_unknown_id(client):
    """GRAPH-04 guard — GET /concepts/99999 returns HTTP 404.

    RED state: concept endpoint returns 501 stub → this test FAILS (gets 501, not 404).
    """
    from app.main import app
    from sqlalchemy.ext.asyncio import AsyncSession

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(side_effect=[
        # concept lookup returns None (not found)
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
    ])

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    try:
        response = await client.get("/concepts/99999")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 404
