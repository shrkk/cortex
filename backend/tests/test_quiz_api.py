"""Tests for quiz API endpoints (Phase 4).

Covers QUIZ-01 through QUIZ-06.
RED state: route integration tests xfail until Wave 2 (04-04-PLAN.md) implements quiz.py.
Pure structural/logic tests (test_quiz_model, test_no_reference_answer_in_quiz_response,
test_question_distribution_formula) pass immediately.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_quiz(id: int = 1, course_id: int = 1, questions: list | None = None):
    q = MagicMock()
    q.id = id
    q.course_id = course_id
    q.questions = questions or []
    return q


def _make_concept(id: int = 1, struggle_signals: dict | None = None, concept_sources: list | None = None):
    c = MagicMock()
    c.id = id
    c.title = f"Concept {id}"
    c.definition = "A concept definition."
    c.gotchas = []
    c.struggle_signals = struggle_signals
    c.concept_sources = concept_sources or []
    return c


# ---------------------------------------------------------------------------
# Structural tests — pass in RED state
# ---------------------------------------------------------------------------

def test_quiz_model():
    """QUIZ-01: Quiz has course_id FK; no concept_id FK (standalone node)."""
    from app.models.models import Quiz
    assert hasattr(Quiz, "course_id"), "Quiz must have course_id (attached to course root)"
    assert not hasattr(Quiz, "concept_id"), "Quiz must NOT have concept_id (standalone node)"
    assert hasattr(Quiz, "questions"), "Quiz must have questions JSON column"


def test_no_reference_answer_in_quiz_response():
    """QUIZ-05/security: _strip_reference_answers removes reference_answer from all questions."""
    from app.api.quiz import _strip_reference_answers
    questions = [
        {"type": "short_answer", "question": "Q?", "reference_answer": "secret", "answered": False},
        {"type": "mcq", "question": "Q2?", "options": ["A", "B"], "correct_index": 0, "answered": False},
    ]
    stripped = _strip_reference_answers(questions)
    assert "reference_answer" not in stripped[0], "reference_answer must be stripped"
    assert "question" in stripped[0], "question field must be preserved after stripping"
    assert "reference_answer" not in stripped[1], "MCQ must not have reference_answer either"
    assert stripped[1]["options"] == ["A", "B"], "options field must be preserved"


def test_strip_handles_empty_list():
    """Edge case: _strip_reference_answers returns [] for empty input."""
    from app.api.quiz import _strip_reference_answers
    assert _strip_reference_answers([]) == []
    assert _strip_reference_answers(None) == []


def test_question_distribution_formula():
    """QUIZ-03: D-16 formula: round(N*0.4) MCQ, round(N*0.3) short_answer, remainder application."""
    # N=7: MCQ=3, short_answer=2, application=2
    n = 7
    mcq = round(n * 0.4)
    short = round(n * 0.3)
    application = n - mcq - short
    assert mcq == 3
    assert short == 2
    assert application == 2
    assert mcq + short + application == n


def test_quiz_router_registered():
    """QUIZ-02: quiz router is accessible as app.api.quiz.router (APIRouter instance)."""
    from app.api.quiz import router
    from fastapi import APIRouter
    assert isinstance(router, APIRouter)


# ---------------------------------------------------------------------------
# Implementation tests — xfail RED until Wave 2
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="RED — Wave 2 (04-04-PLAN.md) implements POST /quiz")
@pytest.mark.asyncio
async def test_create_quiz():
    """QUIZ-02: POST /quiz returns 201 with quiz_id and stripped questions."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    mock_concept = _make_concept(id=1)
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    concept_result = MagicMock()
    concept_result.scalars.return_value.all.return_value = [mock_concept]
    insert_result = MagicMock()
    insert_result.scalar_one.return_value = 1
    mock_session.execute = AsyncMock(side_effect=[concept_result, insert_result])
    mock_session.commit = AsyncMock()

    with patch("app.api.quiz.AsyncSessionLocal", return_value=mock_session):
        with patch("app.api.quiz.anthropic") as mock_anthropic_pkg:
            mock_client = AsyncMock()
            mock_anthropic_pkg.AsyncAnthropic.return_value = mock_client
            tool_block = MagicMock()
            tool_block.type = "tool_use"
            tool_block.input = {"questions": [
                {"type": "mcq", "question": "Q?", "concept_id": 1,
                 "options": ["A", "B", "C", "D"], "correct_index": 0}
            ]}
            mock_msg = MagicMock()
            mock_msg.stop_reason = "tool_use"
            mock_msg.content = [tool_block]
            mock_client.messages.create = AsyncMock(return_value=mock_msg)
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.anthropic_api_key = "test-key"
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.post("/quiz", json={"course_id": 1, "num_questions": 1})

    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert "questions" in data
    assert all("reference_answer" not in q for q in data["questions"])


@pytest.mark.xfail(strict=True, reason="RED — Wave 2 (04-04-PLAN.md) implements GET /quiz/{id}/results")
@pytest.mark.asyncio
async def test_quiz_results():
    """QUIZ-05: GET /quiz/{id}/results returns score + concepts_to_review."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    answered_questions = [
        {"type": "mcq", "question": "Q?", "concept_id": 1, "options": ["A", "B"],
         "correct_index": 0, "answered": True, "answer": "A",
         "grading": {"correct": True, "feedback": "Correct!"}},
        {"type": "short_answer", "question": "Q2?", "concept_id": 2, "answered": True,
         "answer": "some answer", "reference_answer": "secret",
         "grading": {"correct": False, "feedback": "Not quite."}},
    ]
    quiz = _make_quiz(id=1, questions=answered_questions)
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    quiz_result = MagicMock()
    quiz_result.scalar_one_or_none.return_value = quiz
    mock_session.execute = AsyncMock(return_value=quiz_result)

    with patch("app.api.quiz.AsyncSessionLocal", return_value=mock_session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/quiz/1/results")

    assert resp.status_code == 200
    data = resp.json()
    assert "score" in data
    assert "concepts_to_review" in data
    assert all("reference_answer" not in q for q in data.get("questions", []))


@pytest.mark.xfail(strict=True, reason="RED — Wave 2 (04-04-PLAN.md) implements POST /quiz/{id}/answer")
@pytest.mark.asyncio
async def test_answer_persisted():
    """QUIZ-06: POST /quiz/{id}/answer mutates quiz.questions JSON via flag_modified."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    questions = [
        {"question_id": 0, "type": "mcq", "question": "Q?", "concept_id": 1,
         "options": ["A", "B", "C", "D"], "correct_index": 0,
         "answered": False, "answer": None, "grading": None},
    ]
    quiz = _make_quiz(id=1, questions=questions)
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    quiz_result = MagicMock()
    quiz_result.scalar_one_or_none.return_value = quiz
    mock_session.execute = AsyncMock(return_value=quiz_result)
    mock_session.commit = AsyncMock()

    with patch("app.api.quiz.AsyncSessionLocal", return_value=mock_session):
        with patch("sqlalchemy.orm.attributes.flag_modified") as mock_flag_modified:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/quiz/1/answer", json={"question_id": 0, "answer": "A"})

    assert resp.status_code == 200
    mock_flag_modified.assert_called()


@pytest.mark.xfail(strict=True, reason="RED — Wave 2 (04-04-PLAN.md) implements POST /quiz/{id}/answer")
@pytest.mark.asyncio
async def test_free_response_grading():
    """QUIZ-04: Free-response answer graded by Claude via tool_use, returns {correct, feedback}."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    questions = [
        {"question_id": 0, "type": "short_answer", "question": "Explain GD.",
         "concept_id": 1, "reference_answer": "Optimization using gradients.",
         "answered": False, "answer": None, "grading": None},
    ]
    quiz = _make_quiz(id=1, questions=questions)
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    quiz_result = MagicMock()
    quiz_result.scalar_one_or_none.return_value = quiz
    mock_session.execute = AsyncMock(return_value=quiz_result)
    mock_session.commit = AsyncMock()

    grade_tool_block = MagicMock()
    grade_tool_block.type = "tool_use"
    grade_tool_block.input = {"correct": True, "feedback": "Good answer."}
    grade_msg = MagicMock()
    grade_msg.stop_reason = "tool_use"
    grade_msg.content = [grade_tool_block]

    with patch("app.api.quiz.AsyncSessionLocal", return_value=mock_session):
        with patch("app.api.quiz.anthropic") as mock_anthropic_pkg:
            mock_client = AsyncMock()
            mock_anthropic_pkg.AsyncAnthropic.return_value = mock_client
            mock_client.messages.create = AsyncMock(return_value=grade_msg)
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.anthropic_api_key = "test-key"
                with patch("sqlalchemy.orm.attributes.flag_modified"):
                    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                        resp = await ac.post("/quiz/1/answer", json={"question_id": 0, "answer": "Uses gradients."})

    assert resp.status_code == 200
    data = resp.json()
    assert "grading" in data
    assert "correct" in data["grading"]
    assert "feedback" in data["grading"]


@pytest.mark.xfail(strict=True, reason="RED — Wave 2 (04-04-PLAN.md) implements question distribution")
def test_question_distribution():
    """QUIZ-03: Quiz questions use D-16 distribution formula in the LLM prompt."""
    import inspect
    import app.api.quiz as mod
    source = inspect.getsource(mod)
    assert "0.4" in source, "quiz.py must use round(N*0.4) for MCQ count (D-16)"
    assert "0.3" in source, "quiz.py must use round(N*0.3) for short_answer count (D-16)"
