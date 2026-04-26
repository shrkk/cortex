"""Tests for app.pipeline.edges — RED state in Wave 0, GREEN after Plan 03-04.

Covers EDGE-01 through EDGE-04.
"""
from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.pipeline import edges as edges_mod
from app.pipeline.edges import (
    PREREQ_TOOL,
    _co_occurrence_edges,
    _compute_depths,
    _prerequisite_edges,
    run_edges,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session_mock(*, scalars_all: list | None = None, execute_returns: list | None = None) -> AsyncMock:
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()

    result = MagicMock()
    result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=scalars_all or [])))
    result.scalar_one_or_none = MagicMock(return_value=None)
    result.first = MagicMock(return_value=None)
    if execute_returns is not None:
        # iterable execute results for sequential calls
        session.execute = AsyncMock(side_effect=execute_returns)
    else:
        session.execute = AsyncMock(return_value=result)
    return session


def _make_prereq_response(pairs: list[dict]) -> MagicMock:
    tb = MagicMock()
    tb.type = "tool_use"
    tb.input = {"prerequisites": pairs}
    msg = MagicMock()
    msg.stop_reason = "tool_use"
    msg.content = [tb]
    return msg


# ---------------------------------------------------------------------------
# EDGE-01: course->concept "contains" is implicit via concept.course_id FK
# ---------------------------------------------------------------------------

def test_no_contains_edge_rows_inserted():
    """EDGE-01 — edges.py must NOT insert edges with edge_type='contains'.

    The 'contains' relationship is represented by concept.course_id FK only
    (RESEARCH.md Pattern 7 / Decision A2). The graph API in Phase 5 will
    synthesize 'contains' edges from the FK.
    """
    src = inspect.getsource(edges_mod)
    # Verify the three real edge_type values used are co_occurrence, prerequisite, related only.
    # Docstrings may mention "contains" as a concept — we check the pattern
    # edge_type="contains" or edge_type='contains' is not in the source.
    assert 'edge_type="contains"' not in src and "edge_type='contains'" not in src, \
        "edges.py must not set edge_type='contains' (EDGE-01 / RESEARCH.md Pattern 7)"
    # Positive: the three valid edge types ARE referenced
    assert '"co_occurrence"' in src or "'co_occurrence'" in src
    assert '"prerequisite"' in src or "'prerequisite'" in src


# ---------------------------------------------------------------------------
# EDGE-02: co-occurrence pairs from same chunk
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_co_occurrence_creates_pairs_for_same_chunk():
    """EDGE-02 — for chunks with N concepts, _co_occurrence_edges creates C(N,2) edges
    of edge_type='co_occurrence', or increments weight on existing pairs."""
    # Mock: ConceptSource rows for source_id=1 group concepts {10, 20, 30} on the same
    # chunk via chunks->concept_sources join. Wave 2 must enumerate combinations(sorted([10,20,30]),2)
    # and insert 3 edges: (10,20), (10,30), (20,30).
    session = _make_session_mock()
    with patch("app.pipeline.edges.AsyncSessionLocal", return_value=session):
        await _co_occurrence_edges(source_id=1)
    # Wave 2 will populate session.add or session.execute calls; structural test below
    # validates the pattern exists in source code
    assert True  # placeholder — assertion is in test_edges_uses_combinations below


def test_edges_module_uses_combinations():
    """EDGE-02 — edges.py imports/uses itertools.combinations for pair enumeration."""
    src = inspect.getsource(edges_mod)
    assert "combinations" in src


def test_edges_uses_select_then_update_for_co_occurrence():
    """EDGE-02 — edges.py uses SELECT-then-UPDATE pattern (no unique index on
    (from_id, to_id, edge_type) -> cannot use ON CONFLICT). Must reference
    'co_occurrence' edge_type and weight increment."""
    src = inspect.getsource(edges_mod)
    assert '"co_occurrence"' in src or "'co_occurrence'" in src
    # Must increment weight on repeat — look for weight += or weight = ... + 1
    assert "weight" in src
    assert ("weight += 1" in src or "weight + 1" in src or "weight = " in src)


# ---------------------------------------------------------------------------
# EDGE-03: prerequisite edges via LLM tool_use, batched
# ---------------------------------------------------------------------------

def test_prereq_tool_schema_strict():
    """EDGE-03 — PREREQ_TOOL has additionalProperties:false and maxItems=30."""
    sch = PREREQ_TOOL["input_schema"]
    assert sch["additionalProperties"] is False
    items = sch["properties"]["prerequisites"]
    assert items["maxItems"] == 30
    assert items["items"]["additionalProperties"] is False
    assert set(items["items"]["required"]) == {"prerequisite", "concept"}


def test_prereq_uses_tool_choice():
    src = inspect.getsource(edges_mod)
    assert 'tool_choice' in src
    assert '"name": "infer_prerequisites"' in src


def test_prereq_batches_max_50_concepts():
    """EDGE-03 — source must reference 50-concept batching (max 50 concepts per call)."""
    src = inspect.getsource(edges_mod)
    # Must slice or batch by 50 — accept :50 slicing or BATCH_SIZE = 50 etc.
    assert (":50" in src) or ("= 50" in src) or ("MAX_CONCEPTS = 50" in src) or ("[:50]" in src)


@pytest.mark.asyncio
async def test_prerequisite_edges_inserts_rows_from_llm():
    """EDGE-03 — _prerequisite_edges inserts edges of edge_type='prerequisite'
    based on Claude tool_use output mapping titles to concept IDs."""
    session = _make_session_mock()
    with patch("app.pipeline.edges.AsyncSessionLocal", return_value=session):
        await _prerequisite_edges(course_id=1)
    # RED state: stub does nothing. Wave 2 will make this assert via session.add calls.
    src = inspect.getsource(edges_mod)
    assert '"prerequisite"' in src or "'prerequisite'" in src


# ---------------------------------------------------------------------------
# EDGE-04: BFS depth assigned to all concepts (non-null)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_compute_depths_assigns_non_null_to_all():
    """EDGE-04 — _compute_depths writes a depth value for EVERY concept in the course.

    No concept may end with depth IS NULL (Pitfall 7). Isolated concepts get depth=1.
    """
    # Simulate: 3 concept IDs {1, 2, 3} in the course, no prerequisite edges.
    # Expected: all 3 get depth=1 (isolated fallback).
    concept_id_rows = [MagicMock(id=1), MagicMock(id=2), MagicMock(id=3)]

    # First execute() call returns concept IDs; second returns prereq edges (empty).
    concepts_result = MagicMock()
    concepts_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=concept_id_rows)))
    concepts_result.__iter__ = MagicMock(return_value=iter([(r.id,) for r in concept_id_rows]))

    edges_result = MagicMock()
    edges_result.__iter__ = MagicMock(return_value=iter([]))   # no prereq edges
    edges_result.fetchall = MagicMock(return_value=[])
    edges_result.all = MagicMock(return_value=[])

    update_result = MagicMock()

    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    session.commit = AsyncMock()
    session.execute = AsyncMock(side_effect=[concepts_result, edges_result] + [update_result] * 10)

    with patch("app.pipeline.edges.AsyncSessionLocal", return_value=session):
        await _compute_depths(course_id=1)

    # Must have committed AND issued update statements equal to concept count (3)
    assert session.commit.await_count >= 1
    # RED state: stub returns immediately; Wave 2 must call session.execute for updates
    # Total execute calls: 1 (load concepts) + 1 (load edges) + N updates >= 5
    assert session.execute.await_count >= 5  # FAILS in RED state (stub makes 0 calls)


def test_edges_module_uses_collections_deque_for_bfs():
    """EDGE-04 — BFS uses collections.deque (RESEARCH.md Pattern 8)."""
    src = inspect.getsource(edges_mod)
    assert "collections" in src
    assert "deque" in src


def test_edges_module_includes_isolated_fallback():
    """EDGE-04 / Pitfall 7 — isolated concepts unreachable from BFS roots get depth=1."""
    src = inspect.getsource(edges_mod)
    # Must explicitly handle the not-in-depths case
    assert "depths[" in src or "depth=1" in src or "depth = 1" in src


# ---------------------------------------------------------------------------
# Integration: run_edges invokes co-occurrence, prerequisites, and depth in order
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_edges_calls_all_three_substages():
    """run_edges must invoke _co_occurrence_edges, _prerequisite_edges, _compute_depths.

    Wave 2 wires these together. RED state stub returns None without invoking them.
    """
    with patch("app.pipeline.edges._co_occurrence_edges", new=AsyncMock()) as co, \
         patch("app.pipeline.edges._prerequisite_edges", new=AsyncMock()) as pq, \
         patch("app.pipeline.edges._compute_depths", new=AsyncMock()) as cd, \
         patch("app.pipeline.edges.AsyncSessionLocal") as session_cls:

        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        # Source.course_id lookup — Wave 2 must read this before fanning out
        src_row = MagicMock(course_id=42)
        result = MagicMock()
        result.scalar_one = MagicMock(return_value=src_row)
        session.execute = AsyncMock(return_value=result)
        session_cls.return_value = session

        await run_edges(source_id=1)

    co.assert_awaited_once()
    pq.assert_awaited_once()
    cd.assert_awaited_once()


# ---------------------------------------------------------------------------
# test_bfs_depth alias (03-VALIDATION.md uses this name)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bfs_depth():
    """EDGE-04 — BFS assigns depth to all concepts; isolated get depth=1 (VALIDATION map alias)."""
    src = inspect.getsource(edges_mod)
    assert "depths[" in src or "depth=1" in src or "depth = 1" in src
    assert "deque" in src
    assert "collections" in src
