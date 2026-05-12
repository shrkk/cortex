#!/usr/bin/env python3
"""
One-shot concept merger for an existing course.

Runs the same cosine + LLM resolution logic as the ingest pipeline over all
concept pairs already in the DB, and merges any that belong together (same
concept, subtopic, or specific variant/application).

Usage (from the backend/ directory):
    python -m scripts.merge_concepts --course-id 1
    python -m scripts.merge_concepts --course-id 1 --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import math
import sys
from dataclasses import dataclass

import anthropic
import sqlalchemy as sa

sys.path.insert(0, str(__file__).rsplit("/scripts/", 1)[0])

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Concept, ConceptSource, Edge, Flashcard
from app.pipeline.resolver import (
    _AUTO_MERGE_DIST,
    _TIEBREAKER_MAX_DIST,
    _llm_tiebreaker,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Union-Find (path-compressed)
# ---------------------------------------------------------------------------

class UnionFind:
    def __init__(self, ids: list[int]) -> None:
        self.parent = {i: i for i in ids}

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


# ---------------------------------------------------------------------------
# Cosine distance (no numpy)
# ---------------------------------------------------------------------------

def _cosine_dist(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 1.0
    return 1.0 - dot / (na * nb)


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------

@dataclass
class ConceptRow:
    id: int
    title: str
    definition: str
    key_points: list
    gotchas: list
    examples: list
    embedding: list[float]
    source_count: int


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def _load_concepts(course_id: int) -> list[ConceptRow]:
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            sa.select(
                Concept.id,
                Concept.title,
                Concept.definition,
                Concept.key_points,
                Concept.gotchas,
                Concept.examples,
                Concept.embedding,
            ).where(
                Concept.course_id == course_id,
                Concept.embedding.isnot(None),
            ).order_by(Concept.id)
        )).all()

        ids = [r.id for r in rows]
        count_rows = (await session.execute(
            sa.select(ConceptSource.concept_id, sa.func.count().label("cnt"))
            .where(ConceptSource.concept_id.in_(ids))
            .group_by(ConceptSource.concept_id)
        )).all() if ids else []
        counts = {r.concept_id: r.cnt for r in count_rows}

    return [
        ConceptRow(
            id=r.id,
            title=r.title,
            definition=r.definition or "",
            key_points=list(r.key_points or []),
            gotchas=list(r.gotchas or []),
            examples=list(r.examples or []),
            embedding=list(r.embedding),
            source_count=counts.get(r.id, 0),
        )
        for r in rows
    ]


async def _do_merge(winner_id: int, loser_id: int) -> None:
    """Merge loser into winner: consolidate JSON, re-home all FK refs, delete loser."""
    async with AsyncSessionLocal() as session:
        winner = await session.get(Concept, winner_id)
        loser  = await session.get(Concept, loser_id)
        if winner is None or loser is None:
            _log.warning("  Concept %d or %d not found — skipping merge.", winner_id, loser_id)
            return

        # Merge JSON fields (dedup, same caps as resolver)
        winner.key_points = list(dict.fromkeys(
            (winner.key_points or []) + (loser.key_points or [])
        ))[:10]
        winner.gotchas = list(dict.fromkeys(
            (winner.gotchas or []) + (loser.gotchas or [])
        ))[:5]
        winner.examples = list(dict.fromkeys(
            (winner.examples or []) + (loser.examples or [])
        ))[:5]

        # Re-home ConceptSource rows (skip duplicate source_ids)
        existing_src_ids = set((await session.execute(
            sa.select(ConceptSource.source_id)
            .where(ConceptSource.concept_id == winner_id)
        )).scalars().all())
        for cs in (await session.execute(
            sa.select(ConceptSource).where(ConceptSource.concept_id == loser_id)
        )).scalars().all():
            if cs.source_id in existing_src_ids:
                await session.delete(cs)
            else:
                cs.concept_id = winner_id

        # Re-home flashcards (bulk)
        await session.execute(
            sa.update(Flashcard)
            .where(Flashcard.concept_id == loser_id)
            .values(concept_id=winner_id)
        )

        # Re-home outgoing edges (loser → X  becomes  winner → X)
        for edge in (await session.execute(
            sa.select(Edge).where(Edge.from_id == loser_id)
        )).scalars().all():
            if edge.to_id == winner_id:            # would become self-loop
                await session.delete(edge)
                continue
            dup = await session.scalar(
                sa.select(Edge).where(
                    Edge.from_id == winner_id,
                    Edge.to_id == edge.to_id,
                    Edge.edge_type == edge.edge_type,
                )
            )
            if dup:
                await session.delete(edge)
            else:
                edge.from_id = winner_id

        # Re-home incoming edges (X → loser  becomes  X → winner)
        for edge in (await session.execute(
            sa.select(Edge).where(Edge.to_id == loser_id)
        )).scalars().all():
            if edge.from_id == winner_id:          # would become self-loop
                await session.delete(edge)
                continue
            dup = await session.scalar(
                sa.select(Edge).where(
                    Edge.from_id == edge.from_id,
                    Edge.to_id == winner_id,
                    Edge.edge_type == edge.edge_type,
                )
            )
            if dup:
                await session.delete(edge)
            else:
                edge.to_id = winner_id

        await session.delete(loser)
        await session.commit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(course_id: int, dry_run: bool) -> None:
    if not settings.anthropic_api_key:
        _log.error("ANTHROPIC_API_KEY must be set.")
        return

    concepts = await _load_concepts(course_id)
    if not concepts:
        _log.info("No concepts with embeddings found for course %d.", course_id)
        return

    _log.info("Loaded %d concepts for course %d.", len(concepts), course_id)
    _log.info("Thresholds: auto-merge dist≤%.2f, tiebreaker dist≤%.2f",
              _AUTO_MERGE_DIST, _TIEBREAKER_MAX_DIST)

    anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    uf = UnionFind([c.id for c in concepts])
    by_id = {c.id: c for c in concepts}

    n_auto = n_llm_merge = n_llm_keep = n_skip = 0

    for i in range(len(concepts)):
        for j in range(i + 1, len(concepts)):
            a, b = concepts[i], concepts[j]
            dist = _cosine_dist(a.embedding, b.embedding)

            if dist <= _AUTO_MERGE_DIST:
                _log.info("AUTO    dist=%.3f  '%s'  ←  '%s'", dist, a.title, b.title)
                uf.union(a.id, b.id)
                n_auto += 1

            elif dist <= _TIEBREAKER_MAX_DIST:
                decision = await _llm_tiebreaker(
                    new_title=b.title,
                    new_definition=b.definition,
                    existing_title=a.title,
                    existing_definition=a.definition,
                    anthropic_client=anthropic_client,
                )
                if decision["same"]:
                    _log.info("MERGE   dist=%.3f  '%s'  ←  '%s'  — %s",
                              dist, a.title, b.title, decision["reason"])
                    uf.union(a.id, b.id)
                    n_llm_merge += 1
                else:
                    _log.info("KEEP    dist=%.3f  '%s'  vs  '%s'  — %s",
                              dist, a.title, b.title, decision["reason"])
                    n_llm_keep += 1
            else:
                n_skip += 1

    _log.info(
        "Pair results: %d auto-merge, %d LLM-merge, %d LLM-keep, %d beyond threshold.",
        n_auto, n_llm_merge, n_llm_keep, n_skip,
    )

    # Build merge groups from union-find
    groups: dict[int, list[int]] = {}
    for cid in by_id:
        groups.setdefault(uf.find(cid), []).append(cid)

    merge_groups = {root: members for root, members in groups.items() if len(members) > 1}

    if not merge_groups:
        _log.info("Nothing to merge.")
        return

    _log.info("%d merge group(s):", len(merge_groups))

    for members in merge_groups.values():
        # Winner: most sources → shortest title (more general) → oldest ID
        winner_id = max(
            members,
            key=lambda cid: (by_id[cid].source_count, -len(by_id[cid].title), -cid),
        )
        losers = [cid for cid in members if cid != winner_id]
        _log.info(
            "  '%s' (id=%d, sources=%d)  absorbs: %s",
            by_id[winner_id].title,
            winner_id,
            by_id[winner_id].source_count,
            [(by_id[l].title, l) for l in losers],
        )

        if dry_run:
            continue

        for loser_id in losers:
            await _do_merge(winner_id, loser_id)
            _log.info("    merged id=%d into id=%d", loser_id, winner_id)

    if dry_run:
        _log.info("DRY RUN — no changes written to DB.")
    else:
        _log.info("Done.")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Merge similar/subtopic concepts within a course."
    )
    ap.add_argument("--course-id", type=int, required=True,
                    help="Course ID to process.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print merge plan without writing to the DB.")
    args = ap.parse_args()
    asyncio.run(run(args.course_id, args.dry_run))


if __name__ == "__main__":
    main()
