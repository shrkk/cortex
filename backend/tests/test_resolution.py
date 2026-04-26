"""Tests for app.pipeline.resolver — RED state in Wave 0, GREEN after Plan 03-03.

Covers RESOLVE-01 through RESOLVE-05.
"""
from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.pipeline import resolver as resolver_mod
from app.pipeline.resolver import (
    TIEBREAKER_TOOL,
    _llm_tiebreaker,
    _resolve_concept,
    run_resolution,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_embed_response(vec: list[float] | None = None) -> MagicMock:
    """Mock openai.embeddings.create response."""
    if vec is None:
        vec = [0.01] * 1536
    data = MagicMock()
    data.embedding = vec
    resp = MagicMock()
    resp.data = [data]
    return resp


def _make_concept_row(*, id: int = 1, title: str = "Existing Concept", definition: str = "Existing def.",
                     dist: float = 0.05) -> MagicMock:
    row = MagicMock()
    row.id = id
    row.title = title
    row.definition = definition
    row.key_points = []
    row.gotchas = []
    row.examples = []
    row.dist = dist
    return row


def _make_tiebreaker_response(same: bool, reason: str = "test") -> MagicMock:
    tb = MagicMock()
    tb.type = "tool_use"
    tb.input = {"same": same, "reason": reason}
    msg = MagicMock()
    msg.stop_reason = "tool_use"
    msg.content = [tb]
    return msg


def _make_session_mock(*, cosine_row: MagicMock | None = None) -> AsyncMock:
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()

    cosine_result = MagicMock()
    cosine_result.first = MagicMock(return_value=cosine_row)
    session.execute = AsyncMock(return_value=cosine_result)
    session.get = AsyncMock(return_value=cosine_row)
    return session


# ---------------------------------------------------------------------------
# RESOLVE-01: course_id always present in cosine query (structural assertion)
# ---------------------------------------------------------------------------

def test_resolver_source_includes_course_id_filter():
    """RESOLVE-01 — resolver.py must always include course_id in cosine queries.

    No cross-course concept merging — single most-critical correctness invariant
    (RESEARCH.md Pitfall 1).
    """
    src = inspect.getsource(resolver_mod)
    # Must filter by course_id in cosine queries
    assert "course_id" in src
    assert "Concept.course_id ==" in src or "Concept.course_id==" in src
    # Must use cosine_distance (not l2_distance — index uses vector_cosine_ops)
    assert "cosine_distance" in src
    assert "l2_distance" not in src


# ---------------------------------------------------------------------------
# RESOLVE-02: high cosine -> auto-merge
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_high_cosine_auto_merge_returns_existing_id():
    """RESOLVE-02 — cosine distance <= 0.08 (similarity >= 0.92) -> merge with existing."""
    existing = _make_concept_row(id=42, dist=0.05)
    session = _make_session_mock(cosine_row=existing)
    mock_openai = AsyncMock()
    mock_openai.embeddings.create = AsyncMock(return_value=_make_embed_response())
    mock_anthropic = AsyncMock()

    with patch("app.pipeline.resolver.AsyncSessionLocal", return_value=session):
        canonical_id = await _resolve_concept(
            title="Gradient Descent",
            definition="Optimization algorithm.",
            key_points=["new point"],
            gotchas=[],
            examples=[],
            related_concepts=[],
            course_id=7,
            source_id=99,
            student_questions=None,
            openai_client=mock_openai,
            anthropic_client=mock_anthropic,
        )

    assert canonical_id == 42
    # Tiebreaker LLM must NOT have been called for high-cosine path
    mock_anthropic.messages.create.assert_not_called()


# ---------------------------------------------------------------------------
# RESOLVE-03: mid cosine -> LLM tiebreaker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mid_cosine_calls_tiebreaker_and_merges_when_same():
    """RESOLVE-03 — 0.08 < dist <= 0.20 -> call LLM tiebreaker; merge if same=true."""
    existing = _make_concept_row(id=77, dist=0.15)
    session = _make_session_mock(cosine_row=existing)
    mock_openai = AsyncMock()
    mock_openai.embeddings.create = AsyncMock(return_value=_make_embed_response())
    mock_anthropic = AsyncMock()
    mock_anthropic.messages.create = AsyncMock(return_value=_make_tiebreaker_response(same=True))

    with patch("app.pipeline.resolver.AsyncSessionLocal", return_value=session):
        canonical_id = await _resolve_concept(
            title="GD", definition="x", key_points=[], gotchas=[], examples=[], related_concepts=[],
            course_id=1, source_id=1, student_questions=None,
            openai_client=mock_openai, anthropic_client=mock_anthropic,
        )

    assert canonical_id == 77
    mock_anthropic.messages.create.assert_called_once()


@pytest.mark.asyncio
async def test_mid_cosine_creates_new_when_tiebreaker_says_different():
    """RESOLVE-03 — when tiebreaker returns same=false, create a new concept (don't merge)."""
    existing = _make_concept_row(id=77, dist=0.15)
    session = _make_session_mock(cosine_row=existing)
    mock_openai = AsyncMock()
    mock_openai.embeddings.create = AsyncMock(return_value=_make_embed_response())
    mock_anthropic = AsyncMock()
    mock_anthropic.messages.create = AsyncMock(return_value=_make_tiebreaker_response(same=False))

    with patch("app.pipeline.resolver.AsyncSessionLocal", return_value=session):
        canonical_id = await _resolve_concept(
            title="Different", definition="x", key_points=[], gotchas=[], examples=[], related_concepts=[],
            course_id=1, source_id=1, student_questions=None,
            openai_client=mock_openai, anthropic_client=mock_anthropic,
        )

    # New concept created -> session.add was called for the new Concept row
    assert canonical_id != 77
    assert session.add.called


# ---------------------------------------------------------------------------
# RESOLVE-04: low cosine -> create new
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_low_cosine_creates_new_concept():
    """RESOLVE-04 — dist > 0.20 (similarity < 0.80) -> create new concept; no tiebreaker."""
    existing = _make_concept_row(id=11, dist=0.55)
    session = _make_session_mock(cosine_row=existing)
    mock_openai = AsyncMock()
    mock_openai.embeddings.create = AsyncMock(return_value=_make_embed_response())
    mock_anthropic = AsyncMock()

    with patch("app.pipeline.resolver.AsyncSessionLocal", return_value=session):
        canonical_id = await _resolve_concept(
            title="Brand New", definition="Fresh concept.",
            key_points=[], gotchas=[], examples=[], related_concepts=[],
            course_id=1, source_id=1, student_questions=None,
            openai_client=mock_openai, anthropic_client=mock_anthropic,
        )

    assert canonical_id != 11
    mock_anthropic.messages.create.assert_not_called()
    assert session.add.called


@pytest.mark.asyncio
async def test_no_existing_concepts_creates_new():
    """RESOLVE-04 edge case — when course has zero existing concepts (cosine query returns None)."""
    session = _make_session_mock(cosine_row=None)
    mock_openai = AsyncMock()
    mock_openai.embeddings.create = AsyncMock(return_value=_make_embed_response())
    mock_anthropic = AsyncMock()

    with patch("app.pipeline.resolver.AsyncSessionLocal", return_value=session):
        canonical_id = await _resolve_concept(
            title="First Concept", definition="d",
            key_points=[], gotchas=[], examples=[], related_concepts=[],
            course_id=42, source_id=1, student_questions=None,
            openai_client=mock_openai, anthropic_client=mock_anthropic,
        )

    assert session.add.called
    assert isinstance(canonical_id, int)


# ---------------------------------------------------------------------------
# RESOLVE-01 (semantic): tiebreaker tool schema strict
# ---------------------------------------------------------------------------

def test_tiebreaker_tool_schema_strict():
    """TIEBREAKER_TOOL has additionalProperties:false and forces (same, reason)."""
    sch = TIEBREAKER_TOOL["input_schema"]
    assert sch["additionalProperties"] is False
    assert set(sch["required"]) == {"same", "reason"}
    assert sch["properties"]["same"]["type"] == "boolean"


@pytest.mark.asyncio
async def test_tiebreaker_uses_force_tool_choice():
    """RESOLVE-03 — _llm_tiebreaker source must use tool_choice forcing decide_merge."""
    src = inspect.getsource(resolver_mod)
    assert 'tool_choice' in src
    assert '"name": "decide_merge"' in src


# ---------------------------------------------------------------------------
# RESOLVE-05: same-topic in same course -> ONE concept; same-topic across courses -> TWO
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve05_dedupes_within_course():
    """RESOLVE-05 — second 'Gradient Descent' in same course returns the existing concept_id."""
    # Simulate: existing concept at very-low dist (similarity ~0.95)
    existing = _make_concept_row(id=500, title="Gradient Descent", definition="Optimization", dist=0.04)
    session = _make_session_mock(cosine_row=existing)
    mock_openai = AsyncMock()
    mock_openai.embeddings.create = AsyncMock(return_value=_make_embed_response())
    mock_anthropic = AsyncMock()

    with patch("app.pipeline.resolver.AsyncSessionLocal", return_value=session):
        canonical_id = await _resolve_concept(
            title="Gradient Descent", definition="Optimization technique.",
            key_points=[], gotchas=[], examples=[], related_concepts=[],
            course_id=42, source_id=2, student_questions=None,
            openai_client=mock_openai, anthropic_client=mock_anthropic,
        )

    assert canonical_id == 500  # merged, not duplicated


@pytest.mark.asyncio
async def test_resolve05_two_courses_produce_separate_concepts():
    """RESOLVE-05 behavioral — identical title in different courses -> two separate concept rows.

    When course_id=1 has no existing near-match AND course_id=2 has no existing near-match,
    RESOLVE-04 triggers for both, creating two independent concept rows.
    The resolver must never query concepts from course_id=2 when processing course_id=1.
    """
    mock_openai = AsyncMock()
    mock_openai.embeddings.create = AsyncMock(return_value=_make_embed_response())

    # course_id=1: no near-match -> creates new concept; stub returns 0
    session1 = _make_session_mock(cosine_row=None)
    with patch("app.pipeline.resolver.AsyncSessionLocal", return_value=session1):
        id1 = await _resolve_concept(
            title="Gradient Descent", definition="Optimization technique.",
            key_points=[], gotchas=[], examples=[], related_concepts=[],
            course_id=1, source_id=1, student_questions=None,
            openai_client=mock_openai, anthropic_client=AsyncMock(),
        )

    # course_id=2: also no near-match -> creates a second separate concept row; stub returns 0
    session2 = _make_session_mock(cosine_row=None)
    with patch("app.pipeline.resolver.AsyncSessionLocal", return_value=session2):
        id2 = await _resolve_concept(
            title="Gradient Descent", definition="Optimization technique.",
            key_points=[], gotchas=[], examples=[], related_concepts=[],
            course_id=2, source_id=2, student_questions=None,
            openai_client=mock_openai, anthropic_client=AsyncMock(),
        )

    # Wave 1 must: session.add() called for both courses (no cross-course merging)
    assert session1.add.called, "Should have called session.add for course 1 concept"
    assert session2.add.called, "Should have called session.add for course 2 concept"


def test_resolver_uses_title_plus_definition_for_embedding():
    """RESOLVE-05 / Pitfall 4 — embeds 'title + definition' (NOT title alone)."""
    src = inspect.getsource(resolver_mod)
    # Must concatenate title and definition before embedding (Pattern in RESEARCH.md uses
    # f"{title}. {definition}")
    assert ("title" in src and "definition" in src)
    # The string concatenation/format pattern
    assert ('f"{title}' in src) or ('f"{title}.' in src) or ('title + ' in src) or ('title} {definition}' in src)


# ---------------------------------------------------------------------------
# RESOLVE-01: test_course_scope alias (03-VALIDATION.md uses this name)
# ---------------------------------------------------------------------------

def test_course_scope():
    """RESOLVE-01 — resolver.py always includes course_id scoping (alias for VALIDATION map)."""
    src = inspect.getsource(resolver_mod)
    assert "course_id" in src
    assert "Concept.course_id ==" in src or "Concept.course_id==" in src
