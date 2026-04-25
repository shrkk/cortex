import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

EXPECTED_TABLES = {
    "users",
    "courses",
    "sources",
    "chunks",
    "concepts",
    "concept_sources",
    "extraction_cache",
    "edges",
    "flashcards",
    "quizzes",
}


async def test_all_tables_exist(db_engine):
    async with db_engine.connect() as conn:
        table_names = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
    missing = EXPECTED_TABLES - set(table_names)
    assert missing == set(), f"Missing tables: {missing}"


async def test_vector_extension_installed(db_engine):
    async with db_engine.connect() as conn:
        result = await conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        )
        row = result.fetchone()
    assert row is not None, "pgvector extension not installed"


async def test_hnsw_index_exists(db_engine):
    async with db_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'concepts' AND indexname = 'concepts_embedding_idx'"
            )
        )
        row = result.fetchone()
    assert row is not None, "hnsw index concepts_embedding_idx not found on concepts table"
