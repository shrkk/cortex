"""
Cortex edge inference pipeline stage.

EDGE-01: course->concept "contains" relationship is implicit via concept.course_id FK
         (NOT stored in edges table — see RESEARCH.md Pattern 7).
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
from itertools import combinations
from typing import Any

import anthropic
import sqlalchemy as sa

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Concept, ConceptSource, Edge, Source

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
    """Stub — Wave 2 enumerates all (a, b) pairs of concepts from same chunk and
    SELECT-then-UPDATE weights in the edges table.

    Pattern: for a, b in combinations(sorted(concept_ids), 2):
        existing = SELECT Edge WHERE from_id=a AND to_id=b AND edge_type='co_occurrence'
        if existing: existing.weight += 1.0
        else: session.add(Edge(from_id=a, to_id=b, edge_type="co_occurrence", weight=1.0))
    """
    return None


async def _prerequisite_edges(course_id: int) -> None:
    """Stub — Wave 2 batches up to 50 concepts per LLM call and inserts prerequisite edges.

    tool_choice forces 'infer_prerequisites' tool use (EDGE-03).
    Output pairs map concept titles -> concept IDs for edge insertion.

    Wave 2 implementation outline:
      # Batch: max 50 concepts per call (EDGE-03)
      concept_list = "\n".join(f"- {c.title}" for c in concepts[:50])
      message = await client.messages.create(
          model="claude-sonnet-4-6",
          max_tokens=2048,
          tools=[PREREQ_TOOL],
          tool_choice={"type": "tool", "name": "infer_prerequisites"},
          messages=[{"role": "user", "content": ...}],
      )
      tool_block = next(b for b in message.content if b.type == "tool_use")
      for pair in tool_block.input["prerequisites"]:
          a_id = title_to_id.get(pair["prerequisite"])
          b_id = title_to_id.get(pair["concept"])
          if a_id and b_id:
              session.add(Edge(
                  from_id=a_id, to_id=b_id, edge_type="prerequisite", weight=1.0
              ))
    """
    return None


async def _compute_depths(course_id: int) -> None:
    """Stub — Wave 2 runs Python BFS via collections.deque over prerequisite edges.

    Algorithm:
      - roots = concepts in course that are NOT a 'to_id' in any prerequisite edge
      - depth[root] = 1
      - BFS: depth[child] = depth[parent] + 1 along prerequisite edges
      - any concept not visited by BFS gets depth=1 (isolated fallback)

    Wave 2 implementation outline:
      async with AsyncSessionLocal() as session:
          concepts_result = await session.execute(
              sa.select(Concept.id).where(Concept.course_id == course_id)
          )
          concept_ids = {row.id for row in concepts_result}

          edges_result = await session.execute(
              sa.select(Edge.from_id, Edge.to_id)
              .where(
                  Edge.edge_type == "prerequisite",
                  Edge.from_id.in_(concept_ids),
                  Edge.to_id.in_(concept_ids),
              )
          )
          children: dict[int, set[int]] = collections.defaultdict(set)
          has_prereq: set[int] = set()
          for from_id, to_id in edges_result:
              children[from_id].add(to_id)
              has_prereq.add(to_id)

          # BFS from roots — concepts with no incoming prerequisite edges
          depths: dict[int, int] = {}
          roots = concept_ids - has_prereq
          queue: collections.deque = collections.deque()
          for root_id in roots:
              depths[root_id] = 1
              queue.append(root_id)

          while queue:
              node_id = queue.popleft()
              for child_id in children[node_id]:
                  if child_id not in depths:
                      depths[child_id] = depths[node_id] + 1
                      queue.append(child_id)

          # Isolated fallback — assign depth=1 to any unreachable concept (EDGE-04 Pitfall 7)
          for cid in concept_ids:
              if cid not in depths:
                  depths[cid] = 1

          # Batch UPDATE all depths
          for cid, depth in depths.items():
              await session.execute(
                  sa.update(Concept).where(Concept.id == cid).values(depth=depth)
              )
          await session.commit()

    Concepts batched at most [:50] per LLM call for prerequisite inference (EDGE-03).
    """
    return None


async def run_edges(source_id: int) -> None:
    """Stub — Wave 2 orchestrates: co-occurrence (per source) -> prerequisite (per
    course, idempotent) -> BFS depth (per course)."""
    return None


async def _stage_edges(source_id: int) -> None:
    """Orchestrator-facing alias. pipeline.py calls this name."""
    await run_edges(source_id)
