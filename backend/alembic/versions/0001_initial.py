"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-25

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # MUST be first — all Vector column CREATE TABLE statements fail without this extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "courses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "course_id",
            sa.Integer,
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String, nullable=False),
        sa.Column("title", sa.String),
        sa.Column("source_uri", sa.Text),
        sa.Column("raw_text", sa.Text),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("status", sa.String, server_default="pending", nullable=False),
        sa.Column("error", sa.Text),
        sa.Column("metadata", sa.JSON),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "source_id",
            sa.Integer,
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("page_num", sa.Integer),
        sa.Column("embedding", Vector(1536)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "concepts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "course_id",
            sa.Integer,
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("definition", sa.Text),
        sa.Column("key_points", sa.JSON),
        sa.Column("gotchas", sa.JSON),
        sa.Column("examples", sa.JSON),
        sa.Column("related_concepts", sa.JSON),
        sa.Column("embedding", Vector(1536)),
        sa.Column("depth", sa.Integer),
        sa.Column("struggle_signals", sa.JSON),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "concept_sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "concept_id",
            sa.Integer,
            sa.ForeignKey("concepts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            sa.Integer,
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("student_questions", sa.JSON),
    )

    op.create_table(
        "extraction_cache",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("chunk_hash", sa.String(64), nullable=False),
        sa.Column("model_version", sa.String, nullable=False),
        sa.Column("extracted_concepts", sa.JSON),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "edges",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("from_id", sa.Integer, nullable=False),
        sa.Column("to_id", sa.Integer, nullable=False),
        sa.Column("edge_type", sa.String, nullable=False),
        sa.Column("weight", sa.Float, server_default="1.0"),
        sa.Column("metadata", sa.JSON),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "flashcards",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "concept_id",
            sa.Integer,
            sa.ForeignKey("concepts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("front", sa.Text, nullable=False),
        sa.Column("back", sa.Text, nullable=False),
        sa.Column("card_type", sa.String, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "quizzes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "course_id",
            sa.Integer,
            sa.ForeignKey("courses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("questions", sa.JSON),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # hnsw index on concepts.embedding — SAFE on empty table (unlike ivfflat)
    # m=16, ef_construction=64 are standard starting values per pgvector docs
    # Uses vector_cosine_ops for cosine similarity (concept resolution uses cosine)
    op.execute(
        """
        CREATE INDEX concepts_embedding_idx
        ON concepts USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # Unique index for extraction_cache lookup by (chunk_hash, model_version)
    op.create_index(
        "ix_extraction_cache_chunk_model",
        "extraction_cache",
        ["chunk_hash", "model_version"],
        unique=True,
    )

    # Index on sources.content_hash for O(log n) dedup lookups
    op.create_index("ix_sources_content_hash", "sources", ["content_hash"])

    # NOTE: ivfflat index for chunks.embedding is intentionally DEFERRED.
    # ivfflat requires data to build clusters — on an empty table it has near-zero recall.
    # Create it in a separate migration after seed_demo.py has loaded data.


def downgrade() -> None:
    # Drop indexes first, then tables in reverse FK dependency order
    op.drop_index("ix_sources_content_hash", table_name="sources")
    op.drop_index("ix_extraction_cache_chunk_model", table_name="extraction_cache")
    # concepts_embedding_idx is dropped automatically when the table drops
    op.drop_table("quizzes")
    op.drop_table("flashcards")
    op.drop_table("edges")
    op.drop_table("extraction_cache")
    op.drop_table("concept_sources")
    op.drop_table("concepts")
    op.drop_table("chunks")
    op.drop_table("sources")
    op.drop_table("courses")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
