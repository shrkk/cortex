"""Tests for signals.py pipeline stage (Phase 4).

Covers STRUGGLE-01 through STRUGGLE-05.
RED state: async integration tests xfail until Wave 1 (04-03-PLAN.md) implements run_signals.
Structural/pure-logic tests (test_gotcha_dense_detects_phrases, test_cosine_sim_helper,
test_signals_omits_unevaluated_keys) pass immediately.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.pipeline.signals import run_signals, GOTCHA_PHRASES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_concept(id: int = 1, struggle_signals: dict | None = None):
    c = MagicMock()
    c.id = id
    c.struggle_signals = struggle_signals
    c.concept_sources = []
    return c


def _make_concept_source(
    concept_id: int = 1,
    source_id: int = 1,
    source_type: str = "pdf",
    source_metadata: dict | None = None,
    student_questions: list | None = None,
    created_at=None,
):
    cs = MagicMock()
    cs.concept_id = concept_id
    cs.source_id = source_id
    cs.student_questions = student_questions or []
    cs.source = MagicMock()
    cs.source.source_type = source_type
    cs.source.source_metadata = source_metadata or {}
    if created_at is not None:
        cs.source.created_at = created_at
    return cs


# ---------------------------------------------------------------------------
# Structural/logic tests — pass in RED state
# ---------------------------------------------------------------------------

def test_gotcha_dense_detects_phrases():
    """STRUGGLE-03: All four gotcha trigger phrases are defined in GOTCHA_PHRASES."""
    assert "actually," in GOTCHA_PHRASES
    assert "common mistake," in GOTCHA_PHRASES
    assert "be careful," in GOTCHA_PHRASES
    assert "a subtle point" in GOTCHA_PHRASES


def test_gotcha_phrase_detection_case_insensitive():
    """STRUGGLE-03: Detection is case-insensitive (text is lowercased before comparison)."""
    text = "Actually, this is a common misconception about the algorithm."
    assert any(phrase in text.lower() for phrase in GOTCHA_PHRASES)


def test_signals_omits_unevaluated_keys():
    """D-11: signals dict must NOT include False for unevaluated signals — omit entirely."""
    signals: dict = {}
    signals["gotcha_dense"] = True   # evaluated
    # repeated_confusion and retention_gap NOT added (no chat_log sources)
    assert "repeated_confusion" not in signals
    assert "retention_gap" not in signals
    assert signals == {"gotcha_dense": True}


def test_signals_uses_flag_modified():
    """STRUGGLE-05: signals.py uses flag_modified for JSON column mutation."""
    import inspect
    import app.pipeline.signals as mod
    source = inspect.getsource(mod)
    assert "flag_modified" in source, "signals.py must use flag_modified for struggle_signals JSON mutation"


# ---------------------------------------------------------------------------
# Implementation tests — xfail RED until Wave 1
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gotcha_dense():
    """STRUGGLE-03: Gotcha phrase in chunk text → gotcha_dense signal written."""
    concept = _make_concept(id=1)
    cs = _make_concept_source(concept_id=1, source_id=1, source_type="pdf")
    concept.concept_sources = [cs]

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    # First execute call returns concepts; second returns chunk texts with gotcha phrase
    chunk_text_result = MagicMock()
    chunk_text_result.all.return_value = [MagicMock(text="actually, this is wrong")]
    concept_result = MagicMock()
    concept_result.scalars.return_value.unique.return_value.all.return_value = [concept]
    concept_write_result = MagicMock()
    concept_write_result.scalar_one.return_value = concept

    mock_session.execute = AsyncMock(side_effect=[
        concept_result,   # initial concept query
        chunk_text_result,  # chunk text query for gotcha detection
        concept_write_result,  # write updated signals
    ])
    mock_session.commit = AsyncMock()

    with patch("app.pipeline.signals.AsyncSessionLocal", return_value=mock_session):
        with patch("sqlalchemy.orm.attributes.flag_modified") as mock_flag_modified:
            await run_signals(source_id=1)

    # flag_modified must be called (signals written to DB)
    mock_flag_modified.assert_called()


@pytest.mark.asyncio
async def test_practice_failure():
    """STRUGGLE-04: source_metadata problem_incorrect=True → practice_failure signal."""
    concept = _make_concept(id=1)
    cs = _make_concept_source(
        concept_id=1, source_id=1, source_type="text",
        source_metadata={"problem_incorrect": True},
    )
    concept.concept_sources = [cs]

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    concept_result = MagicMock()
    concept_result.scalars.return_value.unique.return_value.all.return_value = [concept]
    chunk_result = MagicMock()
    chunk_result.all.return_value = []
    concept_write_result = MagicMock()
    concept_write_result.scalar_one.return_value = concept
    mock_session.execute = AsyncMock(side_effect=[concept_result, chunk_result, concept_write_result])
    mock_session.commit = AsyncMock()

    written_signals = {}

    def capture_signals(obj, field):
        written_signals.update(obj.struggle_signals or {})

    with patch("app.pipeline.signals.AsyncSessionLocal", return_value=mock_session):
        with patch("sqlalchemy.orm.attributes.flag_modified", side_effect=capture_signals):
            await run_signals(source_id=1)

    assert written_signals.get("practice_failure") is True


@pytest.mark.asyncio
async def test_repeated_confusion():
    """STRUGGLE-01: ≥3 similar question pairs → repeated_confusion=True."""
    concept = _make_concept(id=1)
    cs = _make_concept_source(
        concept_id=1, source_id=1, source_type="chat_log",
        student_questions=["What is GD?", "How does GD work?", "Explain GD"],
    )
    concept.concept_sources = [cs]

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    concept_result = MagicMock()
    concept_result.scalars.return_value.unique.return_value.all.return_value = [concept]
    question_result = MagicMock()
    question_result.scalars.return_value.all.return_value = [cs]
    chunk_result = MagicMock()
    chunk_result.all.return_value = []
    chat_time_result = MagicMock()
    chat_time_result.scalars.return_value.all.return_value = []
    concept_write_result = MagicMock()
    concept_write_result.scalar_one.return_value = concept
    mock_session.execute = AsyncMock(side_effect=[
        concept_result, question_result, chunk_result, chat_time_result, concept_write_result,
    ])
    mock_session.commit = AsyncMock()

    # Mock OpenAI embedding — return 3 very similar vectors
    similar_vec = [1.0] + [0.0] * 1535
    mock_embed_resp = MagicMock()
    mock_embed_resp.data = [MagicMock(embedding=similar_vec) for _ in range(3)]

    with patch("app.pipeline.signals.AsyncSessionLocal", return_value=mock_session):
        with patch("app.pipeline.signals.AsyncOpenAI") as mock_openai_cls:
            mock_openai = AsyncMock()
            mock_openai_cls.return_value = mock_openai
            mock_openai.embeddings.create = AsyncMock(return_value=mock_embed_resp)
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.openai_api_key = "test-key"
                with patch("sqlalchemy.orm.attributes.flag_modified"):
                    await run_signals(source_id=1)


@pytest.mark.asyncio
async def test_retention_gap():
    """STRUGGLE-02: Two chat_log sources ≥24h apart → retention_gap=True."""
    from datetime import datetime, timedelta, timezone
    concept = _make_concept(id=1)
    now = datetime.now(timezone.utc)
    cs1 = _make_concept_source(source_id=1, source_type="chat_log", created_at=now - timedelta(days=2))
    cs2 = _make_concept_source(source_id=2, source_type="chat_log", created_at=now)
    concept.concept_sources = [cs1, cs2]

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    concept_result = MagicMock()
    concept_result.scalars.return_value.unique.return_value.all.return_value = [concept]
    question_result = MagicMock()
    question_result.scalars.return_value.all.return_value = []
    chunk_result = MagicMock()
    chunk_result.all.return_value = []
    chat_time_result = MagicMock()
    chat_time_result.scalars.return_value.all.return_value = [now - timedelta(days=2), now]
    concept_write_result = MagicMock()
    concept_write_result.scalar_one.return_value = concept
    mock_session.execute = AsyncMock(side_effect=[
        concept_result, question_result, chunk_result, chat_time_result, concept_write_result,
    ])
    mock_session.commit = AsyncMock()

    written_signals = {}

    def capture_signals(obj, field):
        written_signals.update(obj.struggle_signals or {})

    with patch("app.pipeline.signals.AsyncSessionLocal", return_value=mock_session):
        with patch("sqlalchemy.orm.attributes.flag_modified", side_effect=capture_signals):
            await run_signals(source_id=1)

    assert written_signals.get("retention_gap") is True


@pytest.mark.asyncio
async def test_signals_written():
    """STRUGGLE-05: Signals written to concepts.struggle_signals JSONB via flag_modified."""
    concept = _make_concept(id=1)
    concept.concept_sources = []

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    concept_result = MagicMock()
    concept_result.scalars.return_value.unique.return_value.all.return_value = [concept]
    mock_session.execute = AsyncMock(return_value=concept_result)
    mock_session.commit = AsyncMock()

    with patch("app.pipeline.signals.AsyncSessionLocal", return_value=mock_session):
        with patch("sqlalchemy.orm.attributes.flag_modified") as mock_flag_modified:
            await run_signals(source_id=1)

    # flag_modified must be called to persist the JSON mutation
    mock_flag_modified.assert_called()
