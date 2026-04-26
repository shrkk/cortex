"""
Cortex ingestion pipeline — 8 stages.

Phase 2: stages 1-3 (parse, chunk, embed) are real.
Phase 3: stages 4-6 (extract, resolve, edges) are now real (Plans 03-02, 03-03, 03-04).
Stages 7-8 (flashcards, signals) remain no-op stubs until Phase 4.

Each stage opens its own AsyncSessionLocal session (session-per-stage pattern).
Never pass a session across stage boundaries — connection pool exhaustion.
"""
from __future__ import annotations

import hashlib
import traceback

import sqlalchemy as sa
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.models import Chunk, Source


async def run_pipeline(source_id: int, force: bool = False) -> None:
    """Top-level pipeline entrypoint. Called via BackgroundTasks.add_task.

    Args:
        source_id: ID of the Source row to process.
        force: If True, bypass content_hash deduplication check (D-04).
    """
    try:
        await _stage_set_processing(source_id)
        await _stage_parse_and_chunk(source_id, force=force)
        await _stage_embed(source_id)
        await _stage_extract(source_id)
        await _stage_resolve(source_id)
        await _stage_edges(source_id)
        await _stage_flashcards_stub(source_id)
        await _stage_signals_stub(source_id)
        await _stage_set_done(source_id)
    except _DuplicateContent:
        await _stage_set_done(source_id)  # Duplicate is not an error — mark done
    except Exception:
        await _stage_set_error(source_id, traceback.format_exc())


# ---------------------------------------------------------------------------
# Stage 1: Set status=processing
# ---------------------------------------------------------------------------

async def _stage_set_processing(source_id: int) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            sa.update(Source).where(Source.id == source_id).values(status="processing")
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Stage 2: Parse raw_text and create Chunk rows (dedup check here)
# ---------------------------------------------------------------------------

async def _stage_parse_and_chunk(source_id: int, force: bool = False) -> None:
    from app.pipeline.parsers import parse_pdf, parse_url, parse_image, parse_text

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Source).where(Source.id == source_id)
        )
        source: Source = result.scalar_one()

        # Deduplication: sha256 of raw content (PIPE-03)
        content_to_hash = (
            source.raw_text.encode() if source.raw_text
            else source.source_uri.encode() if source.source_uri
            else b""
        )
        content_hash = hashlib.sha256(content_to_hash).hexdigest()

        if not force:
            # Check for existing source with same hash (excluding self) — D-04
            dup_result = await session.execute(
                sa.select(Source.id).where(
                    Source.content_hash == content_hash,
                    Source.id != source_id,
                    Source.status != "error",
                ).limit(1)
            )
            existing_id = dup_result.scalar()
            if existing_id:
                await session.execute(
                    sa.update(Source).where(Source.id == source_id).values(
                        content_hash=content_hash,
                        source_metadata={"duplicate_of": existing_id},
                    )
                )
                await session.commit()
                raise _DuplicateContent(f"Duplicate of source {existing_id}")

        # Update content_hash
        await session.execute(
            sa.update(Source).where(Source.id == source_id).values(
                content_hash=content_hash
            )
        )
        await session.commit()

    # Parse outside the first session (pure I/O)
    async with AsyncSessionLocal() as session:
        result = await session.execute(sa.select(Source).where(Source.id == source_id))
        source = result.scalar_one()

        chunks_data: list[dict] = []
        title: str = source.title or ""

        if source.source_type == "pdf" and source.raw_text:
            # raw_text used as temp storage for file bytes encoded as base64
            # The ingest endpoint stores file bytes in source.raw_text as base64
            import base64
            try:
                data = base64.b64decode(source.raw_text)
            except Exception:
                data = source.raw_text.encode()
            chunks_data, title = await parse_pdf(data, source.title or "upload.pdf")

        elif source.source_type == "url" and source.source_uri:
            chunks_data, title = await parse_url(source.source_uri)

        elif source.source_type == "image" and source.raw_text:
            import base64
            try:
                data = base64.b64decode(source.raw_text)
            except Exception:
                data = source.raw_text.encode()
            chunks_data, title = await parse_image(data, source.title or "image.png")

        elif source.source_type == "text" and source.raw_text:
            chunks_data, title = await parse_text(source.raw_text, source.title)

        # Update source title if not set
        if not source.title and title:
            await session.execute(
                sa.update(Source).where(Source.id == source_id).values(title=title)
            )

        # Create Chunk rows
        for cd in chunks_data:
            chunk = Chunk(
                source_id=source_id,
                text=cd["text"],
                page_num=cd.get("page_num"),
            )
            session.add(chunk)

        await session.commit()


# ---------------------------------------------------------------------------
# Stage 3: Embed all un-embedded chunks for this source
# ---------------------------------------------------------------------------

async def _stage_embed(source_id: int) -> None:
    if not settings.openai_api_key:
        return  # Skip embedding if no API key (dev without key)

    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            sa.select(Chunk).where(
                Chunk.source_id == source_id,
                Chunk.embedding.is_(None),
            )
        )
        chunks = result.scalars().all()

        if not chunks:
            return

        texts = [c.text for c in chunks]
        try:
            # Batch embed all chunks in one API call (text-embedding-3-small, 1536 dims)
            embed_resp = await openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=texts,
            )
        except Exception:
            return  # Embedding is best-effort; invalid/missing key should not fail the pipeline
        for chunk, embed_data in zip(chunks, embed_resp.data):
            chunk.embedding = embed_data.embedding

        await session.commit()


# ---------------------------------------------------------------------------
# Stage 4: Concept extraction (Phase 3, Plan 03-02)
# ---------------------------------------------------------------------------

async def _stage_extract(source_id: int) -> None:
    """Phase 3 Stage 4 — concept extraction. See app.pipeline.extractor."""
    from app.pipeline.extractor import run_extraction
    await run_extraction(source_id)


# ---------------------------------------------------------------------------
# Stage 5: Concept resolution (Phase 3, Plan 03-03)
# ---------------------------------------------------------------------------

async def _stage_resolve(source_id: int) -> None:
    """Phase 3 Stage 5 — concept resolution. See app.pipeline.resolver."""
    from app.pipeline.resolver import run_resolution
    await run_resolution(source_id)


# ---------------------------------------------------------------------------
# Stage 6: Edge inference + BFS depth (Phase 3, Plan 03-04)
# ---------------------------------------------------------------------------

async def _stage_edges(source_id: int) -> None:
    """Phase 3 Stage 6 — edge inference + BFS depth. See app.pipeline.edges."""
    from app.pipeline.edges import run_edges
    await run_edges(source_id)


# ---------------------------------------------------------------------------
# Stage 7–8: Stubs (Phase 4 will replace these)
# ---------------------------------------------------------------------------

async def _stage_flashcards_stub(source_id: int) -> None:
    """Flashcard generation stub — Phase 4 will create flashcard nodes per concept."""
    pass


async def _stage_signals_stub(source_id: int) -> None:
    """Struggle signal stub — Phase 4 will detect and store struggle signals."""
    pass


# ---------------------------------------------------------------------------
# Error and done stages
# ---------------------------------------------------------------------------

async def _stage_set_done(source_id: int) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            sa.update(Source).where(Source.id == source_id).values(status="done")
        )
        await session.commit()


async def _stage_set_error(source_id: int, tb: str) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            sa.update(Source).where(Source.id == source_id).values(
                status="error",
                error=tb[:4000],  # Truncate to fit Text column reasonably
            )
        )
        await session.commit()


class _DuplicateContent(Exception):
    """Raised when content_hash matches an existing source. Pipeline exits early."""
    pass
