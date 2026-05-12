#!/usr/bin/env python3
"""
Backfill flashcards for all existing done sources.

Usage (from the backend/ directory):
    python -m scripts.backfill_flashcards
    python -m scripts.backfill_flashcards --source-id 2
"""
from __future__ import annotations

import argparse
import asyncio
import sys

import sqlalchemy as sa

from app.core.database import AsyncSessionLocal
from app.models.models import Source
from app.pipeline.flashcards import run_flashcards


async def main(source_id: int | None) -> None:
    async with AsyncSessionLocal() as session:
        q = sa.select(Source).where(Source.status == "done")
        if source_id is not None:
            q = q.where(Source.id == source_id)
        sources = (await session.execute(q)).scalars().all()

    if not sources:
        print("No matching sources found.")
        return

    print(f"Backfilling flashcards for {len(sources)} source(s)...")
    for src in sources:
        print(f"  source {src.id} ({src.title})...", end=" ", flush=True)
        await run_flashcards(src.id)
        print("done")

    print("Backfill complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(main(args.source_id))
