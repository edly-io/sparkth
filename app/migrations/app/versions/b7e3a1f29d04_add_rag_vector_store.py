"""add_rag_vector_store

Revision ID: b7e3a1f29d04
Revises: fa552d6ba726
Create Date: 2026-03-25 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op
from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]

# revision identifiers, used by Alembic.
revision: str = "b7e3a1f29d04"
down_revision: Union[str, Sequence[str], None] = "fa552d6ba726"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create rag_document_chunks table
    op.create_table(
        "rag_document_chunks",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')"),
        ),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source_name", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chapter", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column("section", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column("subsection", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("embedding_model", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("embedding_provider", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rag_document_chunks_user_id"), "rag_document_chunks", ["user_id"], unique=False)
    op.create_index("idx_rag_chunks_user_source", "rag_document_chunks", ["user_id", "source_name"], unique=False)

    # Create HNSW index for cosine similarity search
    op.execute("""
        CREATE INDEX idx_rag_chunks_embedding_hnsw
        ON rag_document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_rag_chunks_embedding_hnsw", table_name="rag_document_chunks")
    op.drop_index("idx_rag_chunks_user_source", table_name="rag_document_chunks")
    op.drop_index(op.f("ix_rag_document_chunks_user_id"), table_name="rag_document_chunks")
    op.drop_table("rag_document_chunks")
