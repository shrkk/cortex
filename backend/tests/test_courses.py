"""
Tests for course endpoints: GET /courses, POST /courses, GET /courses/match.

TDD RED phase — these tests are written BEFORE the implementation exists.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.database import get_session


async def test_list_courses_returns_empty_array(client):
    """GET /courses with no courses in DB returns []."""
    response = await client.get("/courses")
    assert response.status_code == 200
    assert response.json() == []


async def test_create_course_returns_course_object(client):
    """POST /courses creates a course and returns the course object with id."""
    from app.main import app

    # Mock the DB session to avoid FK constraint against users table in test DB
    mock_session = AsyncMock()
    # Simulate session.refresh populating the ORM object
    async def mock_refresh(obj):
        obj.id = 42
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
    assert data["title"] == "CS 229: Machine Learning"
    assert data["user_id"] == 1


async def test_create_course_default_user_id_is_1(client):
    """POST /courses without user_id defaults user_id to 1."""
    from app.main import app

    mock_session = AsyncMock()
    async def mock_refresh(obj):
        obj.id = 99
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
            json={"title": "Biology 101"},
        )
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert response.status_code == 201
    assert response.json()["user_id"] == 1


async def test_match_returns_null_when_no_openai_key(client):
    """GET /courses/match?hint=anything returns null when openai_api_key is None."""
    with patch("app.api.courses.settings") as mock_settings:
        mock_settings.openai_api_key = None
        response = await client.get("/courses/match?hint=machine+learning")
    assert response.status_code == 200
    assert response.json() is None


async def test_match_returns_null_when_confidence_below_threshold(client):
    """GET /courses/match returns null when best confidence < 0.65."""
    mock_embed_response = MagicMock()
    mock_embed_response.data = [MagicMock(embedding=[0.1] * 1536)]

    mock_row = MagicMock()
    mock_row.confidence = 0.64  # below threshold

    with patch("app.api.courses.settings") as mock_settings, \
         patch("app.api.courses.AsyncOpenAI") as mock_openai_cls, \
         patch("app.api.courses.AsyncSessionLocal") as mock_session_cls:

        mock_settings.openai_api_key = "sk-test"

        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_embed_response)
        mock_openai_cls.return_value = mock_client

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        response = await client.get("/courses/match?hint=machine+learning")

    assert response.status_code == 200
    assert response.json() is None


async def test_match_returns_course_when_confidence_at_threshold(client):
    """GET /courses/match returns course when confidence == 0.65."""
    mock_embed_response = MagicMock()
    mock_embed_response.data = [MagicMock(embedding=[0.1] * 1536)]

    mock_row = MagicMock()
    mock_row.confidence = 0.65  # at threshold — should return
    mock_row.id = 42
    mock_row.title = "CS 229"

    with patch("app.api.courses.settings") as mock_settings, \
         patch("app.api.courses.AsyncOpenAI") as mock_openai_cls, \
         patch("app.api.courses.AsyncSessionLocal") as mock_session_cls:

        mock_settings.openai_api_key = "sk-test"

        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_embed_response)
        mock_openai_cls.return_value = mock_client

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = mock_row
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        response = await client.get("/courses/match?hint=machine+learning")

    assert response.status_code == 200
    data = response.json()
    assert data is not None
    assert data["course_id"] == 42
    assert data["title"] == "CS 229"
    assert data["confidence"] == 0.65


async def test_match_returns_null_when_no_rows(client):
    """GET /courses/match returns null when no courses have embeddings (fetchone returns None)."""
    mock_embed_response = MagicMock()
    mock_embed_response.data = [MagicMock(embedding=[0.1] * 1536)]

    with patch("app.api.courses.settings") as mock_settings, \
         patch("app.api.courses.AsyncOpenAI") as mock_openai_cls, \
         patch("app.api.courses.AsyncSessionLocal") as mock_session_cls:

        mock_settings.openai_api_key = "sk-test"

        mock_client = AsyncMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_embed_response)
        mock_openai_cls.return_value = mock_client

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None  # no courses with embeddings
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        response = await client.get("/courses/match?hint=machine+learning")

    assert response.status_code == 200
    assert response.json() is None
