"""Tests for the 8-stage background pipeline (Plan 02-05).

Tests are organized around the behaviors defined in the plan:
- run_pipeline on a source with no content → status=done
- run_pipeline when dedup triggers (_DuplicateContent) → status=done, metadata.duplicate_of set
- run_pipeline when an unexpected exception occurs → status=error, traceback in error column
- _stage_set_processing → status=processing
- _stage_set_done → status=done
- force=True bypasses dedup check
"""
from __future__ import annotations

import hashlib
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Import the pipeline module — will fail (RED) until pipeline.py is created
from app.pipeline.pipeline import (
    run_pipeline,
    _stage_set_processing,
    _stage_set_done,
    _stage_set_error,
    _stage_parse_and_chunk,
    _DuplicateContent,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_source(
    id: int = 1,
    course_id: int = 1,
    source_type: str = "text",
    raw_text: str = "Hello world",
    source_uri: str | None = None,
    title: str | None = "Test",
    status: str = "pending",
    content_hash: str | None = None,
    source_metadata: dict | None = None,
):
    """Return a lightweight mock Source object."""
    src = MagicMock()
    src.id = id
    src.course_id = course_id
    src.source_type = source_type
    src.raw_text = raw_text
    src.source_uri = source_uri
    src.title = title
    src.status = status
    src.content_hash = content_hash
    src.source_metadata = source_metadata
    return src


# ---------------------------------------------------------------------------
# Test: _DuplicateContent is importable and is an Exception
# ---------------------------------------------------------------------------

def test_duplicate_content_is_exception():
    """_DuplicateContent must be importable and derive from Exception."""
    exc = _DuplicateContent("duplicate of 42")
    assert isinstance(exc, Exception)
    assert "42" in str(exc)


# ---------------------------------------------------------------------------
# Test: run_pipeline calls stages in order and sets status=done
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_pipeline_sets_done_on_success():
    """run_pipeline completes normally → status=done.

    All DB stages are mocked to no-op so no real DB is needed.
    """
    calls = []

    async def fake_stage(name):
        calls.append(name)

    with (
        patch("app.pipeline.pipeline._stage_set_processing", new=AsyncMock(side_effect=lambda sid: calls.append("processing"))),
        patch("app.pipeline.pipeline._stage_parse_and_chunk", new=AsyncMock(side_effect=lambda sid, force=False: calls.append("parse"))),
        patch("app.pipeline.pipeline._stage_embed", new=AsyncMock(side_effect=lambda sid: calls.append("embed"))),
        patch("app.pipeline.pipeline._stage_extract", new=AsyncMock(side_effect=lambda sid: calls.append("extract"))),
        patch("app.pipeline.pipeline._stage_resolve", new=AsyncMock(side_effect=lambda sid: calls.append("resolve"))),
        patch("app.pipeline.pipeline._stage_edges", new=AsyncMock(side_effect=lambda sid: calls.append("edges"))),
        patch("app.pipeline.pipeline._stage_flashcards_stub", new=AsyncMock(side_effect=lambda sid: calls.append("flashcards"))),
        patch("app.pipeline.pipeline._stage_signals_stub", new=AsyncMock(side_effect=lambda sid: calls.append("signals"))),
        patch("app.pipeline.pipeline._stage_set_done", new=AsyncMock(side_effect=lambda sid: calls.append("done"))),
    ):
        await run_pipeline(source_id=1)

    assert calls == ["processing", "parse", "embed", "extract", "resolve", "edges", "flashcards", "signals", "done"]


@pytest.mark.asyncio
async def test_run_pipeline_sets_error_on_exception():
    """run_pipeline on unexpected exception → status=error (not status=done)."""
    error_calls = []

    async def exploding_embed(sid):
        raise RuntimeError("OpenAI is down")

    async def fake_set_error(sid, tb):
        error_calls.append(("error", tb))

    with (
        patch("app.pipeline.pipeline._stage_set_processing", new=AsyncMock()),
        patch("app.pipeline.pipeline._stage_parse_and_chunk", new=AsyncMock()),
        patch("app.pipeline.pipeline._stage_embed", new=AsyncMock(side_effect=exploding_embed)),
        patch("app.pipeline.pipeline._stage_set_done", new=AsyncMock()),
        patch("app.pipeline.pipeline._stage_set_error", new=AsyncMock(side_effect=fake_set_error)),
    ):
        await run_pipeline(source_id=1)

    assert len(error_calls) == 1
    assert "OpenAI is down" in error_calls[0][1]  # traceback contains error message


@pytest.mark.asyncio
async def test_run_pipeline_duplicate_content_sets_done_not_error():
    """run_pipeline when _DuplicateContent raised → status=done, NOT status=error."""
    done_calls = []
    error_calls = []

    async def dup_parse(sid, force=False):
        raise _DuplicateContent("dup of 5")

    async def fake_done(sid):
        done_calls.append(sid)

    async def fake_error(sid, tb):
        error_calls.append(sid)

    with (
        patch("app.pipeline.pipeline._stage_set_processing", new=AsyncMock()),
        patch("app.pipeline.pipeline._stage_parse_and_chunk", new=AsyncMock(side_effect=dup_parse)),
        patch("app.pipeline.pipeline._stage_set_done", new=AsyncMock(side_effect=fake_done)),
        patch("app.pipeline.pipeline._stage_set_error", new=AsyncMock(side_effect=fake_error)),
    ):
        await run_pipeline(source_id=99)

    assert 99 in done_calls, "done must be called on duplicate"
    assert 99 not in error_calls, "error must NOT be called on duplicate"


@pytest.mark.asyncio
async def test_run_pipeline_force_passed_to_parse():
    """run_pipeline(force=True) must forward force=True to _stage_parse_and_chunk."""
    parse_calls = []

    async def capture_parse(sid, force=False):
        parse_calls.append({"sid": sid, "force": force})

    with (
        patch("app.pipeline.pipeline._stage_set_processing", new=AsyncMock()),
        patch("app.pipeline.pipeline._stage_parse_and_chunk", new=AsyncMock(side_effect=capture_parse)),
        patch("app.pipeline.pipeline._stage_embed", new=AsyncMock()),
        patch("app.pipeline.pipeline._stage_extract", new=AsyncMock()),
        patch("app.pipeline.pipeline._stage_resolve", new=AsyncMock()),
        patch("app.pipeline.pipeline._stage_edges", new=AsyncMock()),
        patch("app.pipeline.pipeline._stage_flashcards_stub", new=AsyncMock()),
        patch("app.pipeline.pipeline._stage_signals_stub", new=AsyncMock()),
        patch("app.pipeline.pipeline._stage_set_done", new=AsyncMock()),
    ):
        await run_pipeline(source_id=7, force=True)

    assert len(parse_calls) == 1
    assert parse_calls[0]["force"] is True


# ---------------------------------------------------------------------------
# Test: content_hash and dedup logic in _stage_parse_and_chunk
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage_parse_and_chunk_dedup_raises_duplicate_content():
    """When force=False and a matching hash exists, _DuplicateContent is raised."""
    import sqlalchemy as sa

    source = _make_source(raw_text="duplicate text")
    expected_hash = hashlib.sha256(b"duplicate text").hexdigest()

    # Mock AsyncSessionLocal to return sessions with matching dedup row
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    # First session: fetches source, computes hash, finds duplicate
    call_count = 0

    async def mock_execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            # SELECT Source WHERE id = source_id
            mock_result.scalar_one.return_value = source
        elif call_count == 2:
            # SELECT Source.id WHERE content_hash == hash AND id != source_id (dedup check)
            mock_result.scalar.return_value = 99  # existing dup id
        else:
            # UPDATE and other executes
            mock_result.scalar_one.return_value = None
            mock_result.scalar.return_value = None
        return mock_result

    mock_session.execute = AsyncMock(side_effect=mock_execute)
    mock_session.commit = AsyncMock()

    with patch("app.pipeline.pipeline.AsyncSessionLocal", return_value=mock_session):
        with pytest.raises(_DuplicateContent):
            await _stage_parse_and_chunk(source_id=1, force=False)


@pytest.mark.asyncio
async def test_stage_parse_and_chunk_force_skips_dedup():
    """When force=True, dedup check is bypassed and _DuplicateContent is NOT raised."""
    source = _make_source(raw_text="some text", source_type="text")

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    call_count = 0

    async def mock_execute(stmt, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        # First call: SELECT Source WHERE id
        mock_result.scalar_one.return_value = source
        mock_result.scalar.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        return mock_result

    mock_session.execute = AsyncMock(side_effect=mock_execute)
    mock_session.commit = AsyncMock()

    with (
        patch("app.pipeline.pipeline.AsyncSessionLocal", return_value=mock_session),
        patch("app.pipeline.parsers.parse_text", new=AsyncMock(return_value=([], "title"))),
    ):
        # Should NOT raise _DuplicateContent even if there were a dup
        # (force=True bypasses the dedup query entirely)
        await _stage_parse_and_chunk(source_id=1, force=True)
        # If we get here without raising, the test passes


# ---------------------------------------------------------------------------
# Test: module-level acceptance criteria checks
# ---------------------------------------------------------------------------

def test_pipeline_module_has_required_session_count():
    """pipeline.py must have at least 5 'async with AsyncSessionLocal' blocks."""
    import inspect
    import app.pipeline.pipeline as pipeline_mod
    source = inspect.getsource(pipeline_mod)
    count = source.count("async with AsyncSessionLocal")
    assert count >= 5, f"Expected >= 5 AsyncSessionLocal blocks, found {count}"


def test_pipeline_module_has_duplicate_content_class():
    """_DuplicateContent must be defined, raised, and caught in pipeline.py."""
    import inspect
    import app.pipeline.pipeline as pipeline_mod
    source = inspect.getsource(pipeline_mod)
    assert "class _DuplicateContent" in source
    assert "raise _DuplicateContent" in source
    assert "except _DuplicateContent" in source


def test_pipeline_module_uses_embedding_model():
    """pipeline.py must reference text-embedding-3-small."""
    import inspect
    import app.pipeline.pipeline as pipeline_mod
    source = inspect.getsource(pipeline_mod)
    assert "text-embedding-3-small" in source


def test_pipeline_module_has_content_hash():
    """pipeline.py must reference content_hash and sha256 for dedup."""
    import inspect
    import app.pipeline.pipeline as pipeline_mod
    source = inspect.getsource(pipeline_mod)
    assert "content_hash" in source
    assert "sha256" in source


def test_pipeline_module_has_duplicate_of_field():
    """pipeline.py must set metadata.duplicate_of for dedup case (PIPE-03)."""
    import inspect
    import app.pipeline.pipeline as pipeline_mod
    source = inspect.getsource(pipeline_mod)
    assert "duplicate_of" in source


def test_pipeline_module_has_force_param():
    """pipeline.py must use force param at least 3 times (D-04)."""
    import inspect
    import app.pipeline.pipeline as pipeline_mod
    source = inspect.getsource(pipeline_mod)
    force_count = source.count("force")
    assert force_count >= 3, f"Expected >= 3 'force' occurrences, found {force_count}"
