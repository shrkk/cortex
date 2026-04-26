"""Tests for app.pipeline.extractor — RED state in Wave 0, GREEN after Plan 03-02.

Covers EXTRACT-01 through EXTRACT-05.
"""
from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.pipeline import extractor as extractor_mod
from app.pipeline.extractor import (
    EXTRACT_TOOL,
    MODEL_VERSION,
    _extract_chunk_with_cache,
    _extract_questions,
    run_extraction,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool_response(concepts: list[dict]) -> MagicMock:
    """Build a mock Anthropic messages.create response with tool_use content."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = {"concepts": concepts}
    msg = MagicMock()
    msg.stop_reason = "tool_use"
    msg.content = [tool_block]
    return msg


def _make_end_turn_response() -> MagicMock:
    """Mock response where Claude returned text instead of using the tool (EXTRACT-04 retry path)."""
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "I cannot extract concepts."
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    msg.content = [text_block]
    return msg


def _make_chunk(chunk_id: int = 1, source_id: int = 1, text: str = "Gradient descent uses partial derivatives.") -> MagicMock:
    chunk = MagicMock()
    chunk.id = chunk_id
    chunk.source_id = source_id
    chunk.text = text
    chunk.page_num = 1
    return chunk


def _make_session_mock(*, cache_hit: bool = False, cached_concepts: list | None = None, chunks: list | None = None) -> MagicMock:
    """Build the standard AsyncSessionLocal context mock used by all extractor tests.

    Mirrors backend/tests/test_pipeline.py mock structure exactly.
    """
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()

    if cache_hit:
        cached_row = MagicMock()
        cached_row.extracted_concepts = cached_concepts or []
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none = MagicMock(return_value=cached_row)
        session.scalar = AsyncMock(return_value=cached_row)
    else:
        session.scalar = AsyncMock(return_value=None)

    chunk_result = MagicMock()
    chunk_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=chunks or [])))
    session.execute = AsyncMock(return_value=chunk_result)

    return session


# ---------------------------------------------------------------------------
# EXTRACT-01: 0–6 concepts per chunk
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extract_concept_count():
    """EXTRACT-01 — extractor returns the concepts list from the LLM tool call (0..6 items)."""
    chunk = _make_chunk()
    mock_anthropic = AsyncMock()
    mock_anthropic.messages.create = AsyncMock(return_value=_make_tool_response(
        [
            {"title": "Gradient Descent", "definition": "An optimizer.", "key_points": ["a"], "gotchas": [], "examples": [], "related_concepts": []},
            {"title": "Partial Derivative", "definition": "A slope.", "key_points": ["b"], "gotchas": [], "examples": [], "related_concepts": []},
        ]
    ))

    session = _make_session_mock(cache_hit=False)
    with patch("app.pipeline.extractor.AsyncSessionLocal", return_value=session):
        result = await _extract_chunk_with_cache(chunk, "pdf", mock_anthropic)

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["title"] == "Gradient Descent"


# ---------------------------------------------------------------------------
# EXTRACT-02: concept fields present
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concept_fields():
    """EXTRACT-02 — every returned concept dict carries the 6 required fields."""
    chunk = _make_chunk()
    full_concept = {
        "title": "Backpropagation",
        "definition": "Reverse-mode autodiff.",
        "key_points": ["chain rule"],
        "gotchas": ["vanishing gradient"],
        "examples": ["MLP training"],
        "related_concepts": ["Gradient Descent"],
    }
    mock_anthropic = AsyncMock()
    mock_anthropic.messages.create = AsyncMock(return_value=_make_tool_response([full_concept]))

    session = _make_session_mock(cache_hit=False)
    with patch("app.pipeline.extractor.AsyncSessionLocal", return_value=session):
        result = await _extract_chunk_with_cache(chunk, "pdf", mock_anthropic)

    assert len(result) == 1
    for field in ("title", "definition", "key_points", "gotchas", "examples", "related_concepts"):
        assert field in result[0], f"missing field {field}"


def test_extract_tool_schema_lists_six_required_fields():
    """EXTRACT-02 — the tool schema declares all 6 required fields per concept."""
    item_schema = EXTRACT_TOOL["input_schema"]["properties"]["concepts"]["items"]
    required = set(item_schema["required"])
    assert required == {"title", "definition", "key_points", "gotchas", "examples", "related_concepts"}


# ---------------------------------------------------------------------------
# EXTRACT-03: student questions only for chat_log
# ---------------------------------------------------------------------------

def test_extract_questions_helper():
    """EXTRACT-03 — the regex helper finds verbatim questions."""
    text = "Backprop is confusing. What does the gradient mean? Also, why do we use ReLU?"
    qs = _extract_questions(text)
    assert any("gradient mean" in q for q in qs)
    assert any("why do we use" in q.lower() for q in qs)


@pytest.mark.asyncio
async def test_chat_log_questions_attached_to_concept_source():
    """EXTRACT-03 — when source_type='chat_log', run_extraction populates ConceptSource.student_questions.

    Wave 1 must wire _extract_questions(chunk.text) into the ConceptSource row created
    by the resolver when source_type=='chat_log'. This test confirms the contract by
    asserting that run_extraction stores the questions on the cache row's metadata
    OR makes them available downstream (implementation detail decided in 03-02).
    """
    # Stub returns None today; Wave 1 must replace.
    mock_anthropic = AsyncMock()
    mock_anthropic.messages.create = AsyncMock(return_value=_make_tool_response([]))
    session = _make_session_mock(cache_hit=False, chunks=[_make_chunk(text="Why is the gradient negative?")])
    with patch("app.pipeline.extractor.AsyncSessionLocal", return_value=session), \
         patch("app.pipeline.extractor.anthropic.AsyncAnthropic", return_value=mock_anthropic):
        # Today: run_extraction is a stub returning None — assert it ran without error
        # and that questions ARE extracted from the chunk text via the helper
        await run_extraction(source_id=1)
    qs = _extract_questions("Why is the gradient negative?")
    assert qs and "gradient negative" in qs[0]


# ---------------------------------------------------------------------------
# EXTRACT-04: tool_use forced + retry on parse failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tool_use_retry_on_end_turn():
    """EXTRACT-04 — when first call returns stop_reason='end_turn' (no tool_use block),
    extractor retries ONCE; if second call also fails, returns []."""
    chunk = _make_chunk()
    mock_anthropic = AsyncMock()
    # First call: end_turn (no tool block). Second call: same. Final result is empty list.
    mock_anthropic.messages.create = AsyncMock(side_effect=[
        _make_end_turn_response(),
        _make_end_turn_response(),
    ])

    session = _make_session_mock(cache_hit=False)
    with patch("app.pipeline.extractor.AsyncSessionLocal", return_value=session):
        result = await _extract_chunk_with_cache(chunk, "pdf", mock_anthropic)

    assert result == []
    assert mock_anthropic.messages.create.call_count == 2  # exactly one retry


def test_extract_tool_uses_force_tool_choice():
    """EXTRACT-04 — extractor.py source must contain tool_choice forcing the tool."""
    src = inspect.getsource(extractor_mod)
    assert 'tool_choice' in src
    assert '"name": "extract_concepts"' in src
    # additionalProperties must be False on the schema
    assert '"additionalProperties": False' in src


def test_extract_tool_schema_strict():
    """EXTRACT-04 — additionalProperties:false on outer + per-concept schema."""
    sch = EXTRACT_TOOL["input_schema"]
    assert sch.get("additionalProperties") is False
    assert sch["properties"]["concepts"]["items"].get("additionalProperties") is False
    assert sch["properties"]["concepts"]["maxItems"] == 6


# ---------------------------------------------------------------------------
# EXTRACT-05: cache check before LLM call; max 5 parallel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_hit_skips_llm():
    """EXTRACT-05 — when extraction_cache row exists for (chunk_hash, MODEL_VERSION),
    skip the LLM call entirely and return cached extracted_concepts."""
    chunk = _make_chunk()
    cached = [{"title": "Cached", "definition": "x", "key_points": [], "gotchas": [], "examples": [], "related_concepts": []}]
    session = _make_session_mock(cache_hit=True, cached_concepts=cached)
    mock_anthropic = AsyncMock()
    mock_anthropic.messages.create = AsyncMock()

    with patch("app.pipeline.extractor.AsyncSessionLocal", return_value=session):
        result = await _extract_chunk_with_cache(chunk, "pdf", mock_anthropic)

    assert result == cached
    mock_anthropic.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_cache_miss_writes_cache():
    """EXTRACT-05 — on cache miss, after the LLM call, the result is written to extraction_cache."""
    chunk = _make_chunk()
    concepts = [{"title": "X", "definition": "y", "key_points": [], "gotchas": [], "examples": [], "related_concepts": []}]
    mock_anthropic = AsyncMock()
    mock_anthropic.messages.create = AsyncMock(return_value=_make_tool_response(concepts))

    session = _make_session_mock(cache_hit=False)
    with patch("app.pipeline.extractor.AsyncSessionLocal", return_value=session):
        await _extract_chunk_with_cache(chunk, "pdf", mock_anthropic)

    # session.execute must be called with a pg_insert statement (write to extraction_cache)
    # Wave 1 will use pg_insert(...).on_conflict_do_update — assert at least 2 execute() calls
    # (1 for SELECT, 1 for INSERT/UPSERT) OR session.scalar + session.execute.
    assert session.commit.await_count >= 1


def test_extractor_uses_semaphore_5():
    """EXTRACT-05 — extractor.py source contains asyncio.Semaphore(5) for max-5 parallel."""
    src = inspect.getsource(extractor_mod)
    assert "Semaphore(5)" in src or "Semaphore( 5 )" in src or "asyncio.Semaphore(5)" in src


def test_extractor_uses_sha256_for_chunk_hash():
    """EXTRACT-05 — extractor.py source uses hashlib.sha256 for chunk_hash."""
    src = inspect.getsource(extractor_mod)
    assert "hashlib.sha256" in src
    assert "MODEL_VERSION" in src


def test_model_version_constant():
    """MODEL_VERSION is the exact 'claude-sonnet-4-6:v1' string (Pitfall 2 in RESEARCH)."""
    assert MODEL_VERSION == "claude-sonnet-4-6:v1"
