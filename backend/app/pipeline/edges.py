"""
Cortex edge inference pipeline stage.

EDGE-01: course->concept "contains" relationship is implicit via concept.course_id FK
         (NOT stored as an edge row — see RESEARCH.md Pattern 7).
EDGE-02: co-occurrence edges between every pair of concepts extracted from same chunk;
         weight increments on repeated co-occurrence (SELECT-then-UPDATE — no unique
         index on edges (from_id,to_id,edge_type)).
EDGE-03: prerequisite edges inferred by Claude tool_use (max 50 concepts/call,
         max 30 edges/output).
EDGE-04: BFS from concepts with no incoming prerequisite edges; assign depth=1 to
         roots and isolated concepts; depth = parent.depth + 1 along prerequisite edges.

Phase 3 Wave 0: stubs only. Wave 2 implements the bodies.
Phase 3 Wave 2 plan: 03-04-PLAN.md.
"""
from __future__ import annotations

import collections
import hashlib
from itertools import combinations
from typing import Any

import anthropic
import sqlalchemy as sa

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Chunk, Concept, ConceptSource, Edge, ExtractionCache, Source
from app.pipeline.extractor import MODEL_VERSION

PREREQ_TOOL: dict[str, Any] = {
    "name": "infer_prerequisites",
    "description": (
        "Given a list of academic concepts from the same course, identify "
        "prerequisite relationships. Concept A is a prerequisite of concept B if "
        "a student must understand A before they can understand B. Use only the "
        "concept titles provided; do not invent new ones. Return at most 30 pairs."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["prerequisites"],
        "properties": {
            "prerequisites": {
                "type": "array",
                "maxItems": 30,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["prerequisite", "concept"],
                    "properties": {
                        "prerequisite": {
                            "type": "string",
                            "description": "Title of the prerequisite concept (must match an input title verbatim).",
                        },
                        "concept": {
                            "type": "string",
                            "description": "Title of the concept that requires it (must match an input title verbatim).",
                        },
                    },
                },
            }
        },
    },
}


async def _co_occurrence_edges(source_id: int) -> None:
    """EDGE-02 — for each chunk in source_id, enumerate concept-pair co-occurrences
    and SELECT-then-UPDATE the edges table.

    NEVER inserts 'contains' edge_type rows (EDGE-01: course->concept relationship
    is implicit via concept.course_id FK — see RESEARCH.md Pattern 7).
    """
    # 1) Load source -> course_id; load all chunks for this source
    async with AsyncSessionLocal() as session:
        src_row = await session.scalar(sa.select(Source).where(Source.id == source_id))
        if src_row is None:
            return
        course_id: int = src_row.course_id

        chunks_result = await session.execute(
            sa.select(Chunk.id, Chunk.text).where(Chunk.source_id == source_id)
        )
        chunk_rows = list(chunks_result.all())

    if not chunk_rows:
        return

    # 2) Batch-load ExtractionCache for all chunks in one query (WR-01: avoid N+1 sessions)
    chunk_hash_to_id: dict[str, int] = {
        hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(): chunk_id
        for chunk_id, chunk_text in chunk_rows
    }
    chunk_hashes = list(chunk_hash_to_id.keys())
    async with AsyncSessionLocal() as session:
        cache_result = await session.execute(
            sa.select(ExtractionCache).where(
                ExtractionCache.chunk_hash.in_(chunk_hashes),
                ExtractionCache.model_version == MODEL_VERSION,
            )
        )
        cache_map: dict[str, ExtractionCache] = {
            r.chunk_hash: r for r in cache_result.scalars()
        }

    chunk_titles_map: dict[int, list[str]] = {}
    for chunk_hash, chunk_id in chunk_hash_to_id.items():
        cached = cache_map.get(chunk_hash)
        if cached is None or cached.extracted_concepts is None:
            continue
        payload = cached.extracted_concepts
        if isinstance(payload, dict):
            concept_dicts = list(payload.get("concepts", []) or [])
        else:
            concept_dicts = list(payload or [])
        titles = [str(cd.get("title", "")).strip() for cd in concept_dicts if cd.get("title")]
        if titles:
            chunk_titles_map[chunk_id] = titles

    if not chunk_titles_map:
        return

    # 3) Resolve titles -> concept_ids in this course (single batch query)
    all_titles = sorted({t for titles in chunk_titles_map.values() for t in titles})
    async with AsyncSessionLocal() as session:
        title_id_rows = await session.execute(
            sa.select(Concept.id, Concept.title)
            .where(
                Concept.course_id == course_id,
                Concept.title.in_(all_titles),
            )
        )
        title_to_id: dict[str, int] = {row.title: row.id for row in title_id_rows}

    # 4) For each chunk, enumerate combinations and SELECT-then-UPDATE in edges table
    async with AsyncSessionLocal() as session:
        for chunk_id, titles in chunk_titles_map.items():
            ids = sorted({title_to_id[t] for t in titles if t in title_to_id})
            if len(ids) < 2:
                continue
            for a, b in combinations(ids, 2):
                # Canonical ordering: a < b (avoid duplicate edges going both ways)
                existing = await session.scalar(
                    sa.select(Edge).where(
                        Edge.from_id == a,
                        Edge.to_id == b,
                        Edge.edge_type == "co_occurrence",
                    )
                )
                if existing is not None:
                    existing.weight = (existing.weight or 1.0) + 1.0
                else:
                    session.add(
                        Edge(
                            from_id=a,
                            to_id=b,
                            edge_type="co_occurrence",
                            weight=1.0,
                        )
                    )
        await session.commit()


async def _prerequisite_edges(course_id: int) -> None:
    """EDGE-03 — Use Claude tool_use to infer prerequisite edges within a course.

    Batched: max 50 concepts per call, max 30 edges output (constrained by tool schema).
    Idempotent: skips inserting an edge that already exists.
    """
    if not settings.anthropic_api_key:
        return

    # 1) Load concepts in this course
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Concept.id, Concept.title).where(Concept.course_id == course_id)
        )
        concept_rows = list(result.all())

    if len(concept_rows) < 2:
        return

    title_to_id: dict[str, int] = {row.title: row.id for row in concept_rows}

    # Load course title for prompt context (Pitfall 5: include course context)
    async with AsyncSessionLocal() as session:
        from app.models.models import Course as CourseModel
        course_obj = await session.scalar(sa.select(CourseModel).where(CourseModel.id == course_id))
        course_title = course_obj.title if course_obj is not None else "this course"

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # 2) Process in batches of 50
    BATCH_SIZE = 50
    for i in range(0, len(concept_rows), BATCH_SIZE):
        batch = concept_rows[i : i + BATCH_SIZE]
        title_list = "\n".join(f"- {row.title}" for row in batch)
        prompt = (
            f"These are concepts from the course '{course_title}'. "
            f"Identify prerequisite relationships within this course only.\n\n"
            f"Concepts:\n{title_list}"
        )

        try:
            message = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                tools=[PREREQ_TOOL],
                tool_choice={"type": "tool", "name": "infer_prerequisites"},
                messages=[{"role": "user", "content": prompt}],
            )
            if message.stop_reason != "tool_use":
                continue
            tool_block = next(
                (b for b in message.content if getattr(b, "type", None) == "tool_use"),
                None,
            )
            if tool_block is None:
                continue
            pairs = list(tool_block.input.get("prerequisites", []) or [])
        except Exception:  # noqa: BLE001
            continue

        # 3) Map titles -> ids; insert edges (skip if exists, edge_type='prerequisite')
        async with AsyncSessionLocal() as session:
            for pair in pairs:
                prereq_title = str(pair.get("prerequisite", "")).strip()
                concept_title = str(pair.get("concept", "")).strip()
                if not prereq_title or not concept_title:
                    continue
                from_id = title_to_id.get(prereq_title)
                to_id = title_to_id.get(concept_title)
                if from_id is None or to_id is None or from_id == to_id:
                    continue
                # Skip if edge already exists (idempotent)
                existing = await session.scalar(
                    sa.select(Edge).where(
                        Edge.from_id == from_id,
                        Edge.to_id == to_id,
                        Edge.edge_type == "prerequisite",
                    )
                )
                if existing is None:
                    session.add(
                        Edge(
                            from_id=from_id,
                            to_id=to_id,
                            edge_type="prerequisite",
                            weight=1.0,
                        )
                    )
            await session.commit()


async def _compute_depths(course_id: int) -> None:
    """EDGE-04 — Python BFS over prerequisite edges; write Concept.depth.

    Roots: concepts with no incoming prerequisite edge. depth=1 for roots.
    BFS: child.depth = parent.depth + 1.
    Isolated/cyclic fallback: any concept not visited gets depth=1 (Pitfall 7).
    """
    # 1) Load all concept IDs in this course
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Concept.id).where(Concept.course_id == course_id)
        )
        concept_ids: set[int] = {r[0] if isinstance(r, tuple) else r for r in result}

    if not concept_ids:
        return

    # 2) Load all prerequisite edges within course
    async with AsyncSessionLocal() as session:
        edges_result = await session.execute(
            sa.select(Edge.from_id, Edge.to_id).where(
                Edge.edge_type == "prerequisite",
                Edge.from_id.in_(concept_ids),
                Edge.to_id.in_(concept_ids),
            )
        )
        edge_rows = list(edges_result)

    children: dict[int, set[int]] = collections.defaultdict(set)
    has_prereq: set[int] = set()
    for row in edge_rows:
        from_id, to_id = (row[0], row[1]) if isinstance(row, tuple) else (row.from_id, row.to_id)
        children[from_id].add(to_id)
        has_prereq.add(to_id)

    # 3) BFS — roots = concepts with no incoming prerequisite
    depths: dict[int, int] = {}
    queue: collections.deque[int] = collections.deque()
    roots = concept_ids - has_prereq
    for root_id in roots:
        depths[root_id] = 1
        queue.append(root_id)

    while queue:
        node_id = queue.popleft()
        for child_id in children.get(node_id, ()):
            if child_id not in depths:
                depths[child_id] = depths[node_id] + 1
                queue.append(child_id)

    # 4) Isolated/cyclic fallback (Pitfall 7) — depth=1 for any unvisited concept
    for cid in concept_ids:
        if cid not in depths:
            depths[cid] = 1

    # 5) Bulk UPDATE Concept.depth — single CASE WHEN statement (WR-02)
    async with AsyncSessionLocal() as session:
        case_expr = sa.case(depths, value=Concept.id)
        await session.execute(
            sa.update(Concept)
            .where(Concept.id.in_(depths.keys()))
            .values(depth=case_expr)
        )
        await session.commit()


async def run_edges(source_id: int) -> None:
    """Stage 6: edge inference for source_id's course.

    Order:
      1. Co-occurrence edges (per-source — uses extraction_cache + chunks)
      2. Prerequisite edges (per-course, LLM, idempotent)
      3. BFS depth (per-course, ALWAYS runs to ensure depth IS NOT NULL)

    Idempotent: re-running on the same source increments co-occurrence weights and
    skips already-existing prerequisite edges.
    """
    # Resolve course_id
    async with AsyncSessionLocal() as session:
        src_row = await session.scalar(sa.select(Source).where(Source.id == source_id))
        if src_row is None:
            return
        course_id: int = src_row.course_id

    await _co_occurrence_edges(source_id)
    await _prerequisite_edges(course_id)
    await _compute_depths(course_id)


async def _stage_edges(source_id: int) -> None:
    """Orchestrator-facing alias. pipeline.py calls this name."""
    await run_edges(source_id)
