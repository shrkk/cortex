"""Tests for flashcards.py pipeline stage (Phase 4).

Covers FLASH-01 through FLASH-06.
RED state: all async tests xfail until Wave 1 (04-02-PLAN.md) implements run_flashcards.
Structural tests (test_no_srs_columns, test_flashcards_uses_semaphore,
test_flashcards_uses_tool_choice) pass immediately.
"""
from __future__ import annotations

import inspect

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.pipeline.flashcards import run_flashcards


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool_response_flashcards(cards: list[dict]) -> MagicMock:
    """Build a mock Anthropic messages.create response with tool_use content."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = {"cards": cards}
    message = MagicMock()
    message.stop_reason = "tool_use"
    message.content = [tool_block]
    return message


def _make_concept(
    id: int = 1,
    title: str = "Gradient Descent",
    definition: str = "An optimization algorithm.",
    gotchas: list | None = None,
    related_concepts: list | None = None,
    flashcards: list | None = None,
):
    c = MagicMock()
    c.id = id
    c.title = title
    c.definition = definition
    c.gotchas = gotchas or []
    c.related_concepts = related_concepts or []
    c.flashcards = flashcards if flashcards is not None else []
    return c


# ---------------------------------------------------------------------------
# Structural tests — pass in RED state (no real impl needed)
# ---------------------------------------------------------------------------

def test_no_srs_columns():
    """FLASH-06: Flashcard model has no due_at, ease_factor, or repetitions columns."""
    from app.models.models import Flashcard
    assert not hasattr(Flashcard, "due_at"), "Flashcard must not have due_at (no SRS)"
    assert not hasattr(Flashcard, "ease_factor"), "Flashcard must not have ease_factor (no SRS)"
    assert not hasattr(Flashcard, "repetitions"), "Flashcard must not have repetitions (no SRS)"


def test_flashcard_has_required_columns():
    """FLASH-03: Flashcard model has concept_id, front, back, card_type."""
    from app.models.models import Flashcard
    assert hasattr(Flashcard, "concept_id")
    assert hasattr(Flashcard, "front")
    assert hasattr(Flashcard, "back")
    assert hasattr(Flashcard, "card_type")


# ---------------------------------------------------------------------------
# Implementation tests — xfail RED until Wave 1
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="RED — Wave 1 (04-02-PLAN.md) implements run_flashcards")
@pytest.mark.asyncio
async def test_flashcard_generation():
    """FLASH-01: run_flashcards generates 3-6 cards per concept via LLM tool_use call."""
    concept = _make_concept(id=1)
    mock_cards = [
        {"front": "What is Gradient Descent?", "back": "An optimization algorithm.", "card_type": "definition"},
        {"front": "Apply Gradient Descent to minimize loss.", "back": "Compute gradient, step opposite direction.", "card_type": "application"},
    ]
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_result = MagicMock()
    mock_result.scalars.return_value.unique.return_value.all.return_value = [concept]
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    import anthropic as anthropic_module
    with patch("app.pipeline.flashcards.AsyncSessionLocal", return_value=mock_session):
        with patch("app.pipeline.flashcards.anthropic") as mock_anthropic_pkg:
            mock_client = AsyncMock()
            mock_anthropic_pkg.AsyncAnthropic.return_value = mock_client
            mock_client.messages.create = AsyncMock(
                return_value=_make_tool_response_flashcards(mock_cards)
            )
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.anthropic_api_key = "test-key"
                await run_flashcards(source_id=1)

    mock_session.add.assert_called()
    mock_session.commit.assert_called()


@pytest.mark.xfail(strict=True, reason="RED — Wave 1 (04-02-PLAN.md) implements run_flashcards")
@pytest.mark.asyncio
async def test_card_types():
    """FLASH-02: Cards include definition, application, and gotcha types."""
    concept = _make_concept(
        id=1,
        gotchas=["Watch out for learning rate too high"],
        related_concepts=["SGD"],
    )
    mock_cards = [
        {"front": "What is it?", "back": "Optimization.", "card_type": "definition"},
        {"front": "Apply it.", "back": "Step down gradient.", "card_type": "application"},
        {"front": "What if learning rate is too high?", "back": "Diverges.", "card_type": "gotcha"},
        {"front": "GD vs SGD?", "back": "GD uses full batch.", "card_type": "compare"},
    ]
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_result = MagicMock()
    mock_result.scalars.return_value.unique.return_value.all.return_value = [concept]
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    with patch("app.pipeline.flashcards.AsyncSessionLocal", return_value=mock_session):
        with patch("app.pipeline.flashcards.anthropic") as mock_anthropic_pkg:
            mock_client = AsyncMock()
            mock_anthropic_pkg.AsyncAnthropic.return_value = mock_client
            mock_client.messages.create = AsyncMock(
                return_value=_make_tool_response_flashcards(mock_cards)
            )
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.anthropic_api_key = "test-key"
                await run_flashcards(source_id=1)

    # Verify all 4 cards were persisted
    assert mock_session.add.call_count == 4


@pytest.mark.xfail(strict=True, reason="RED — Wave 1 (04-02-PLAN.md) implements run_flashcards")
@pytest.mark.asyncio
async def test_idempotency():
    """FLASH-04: Concepts that already have flashcards are skipped (D-04)."""
    existing_card = MagicMock()
    concept_with_cards = _make_concept(id=1, flashcards=[existing_card])

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_result = MagicMock()
    mock_result.scalars.return_value.unique.return_value.all.return_value = [concept_with_cards]
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    with patch("app.pipeline.flashcards.AsyncSessionLocal", return_value=mock_session):
        with patch("app.pipeline.flashcards.anthropic") as mock_anthropic_pkg:
            mock_client = AsyncMock()
            mock_anthropic_pkg.AsyncAnthropic.return_value = mock_client
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.anthropic_api_key = "test-key"
                await run_flashcards(source_id=1)

    # LLM must NOT be called for concepts that already have flashcards
    mock_client.messages.create.assert_not_called()
    mock_session.add.assert_not_called()


@pytest.mark.xfail(strict=True, reason="RED — Wave 1 (04-02-PLAN.md) adds Semaphore(3) to run_flashcards")
def test_flashcards_uses_semaphore():
    """FLASH-01: flashcards.py uses asyncio.Semaphore(3) for D-05 concurrency limit."""
    import app.pipeline.flashcards as mod
    source = inspect.getsource(mod)
    assert "Semaphore(3)" in source, "flashcards.py must use asyncio.Semaphore(3) per D-05"


@pytest.mark.xfail(strict=True, reason="RED — Wave 1 (04-02-PLAN.md) adds tool_choice to run_flashcards")
def test_flashcards_uses_tool_choice():
    """FLASH-01: flashcards.py forces tool_use via tool_choice kwarg (D-01)."""
    import app.pipeline.flashcards as mod
    source = inspect.getsource(mod)
    assert "tool_choice" in source, "flashcards.py must pass tool_choice to client.messages.create"
    assert "generate_flashcards" in source, "flashcards.py must reference 'generate_flashcards' tool name"


@pytest.mark.xfail(strict=True, reason="RED — Wave 1 (04-02-PLAN.md) adds selectinload to run_flashcards")
def test_flashcards_uses_selectinload():
    """FLASH-04: flashcards.py uses selectinload(Concept.flashcards) for async idempotency check."""
    import app.pipeline.flashcards as mod
    source = inspect.getsource(mod)
    assert "selectinload" in source, "flashcards.py must use selectinload for Concept.flashcards eager load"
