"""drop embedding columns from document_chunks

Revision ID: 8caaf9fdbce0
Revises: 8fc79cca199a
Create Date: 2026-05-27 03:28:26.253067

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8caaf9fdbce0"
down_revision: Union[str, Sequence[str], None] = "8fc79cca199a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop HNSW index on embedding column first
    op.drop_index("idx_rag_chunks_embedding_hnsw", table_name="rag_document_chunks", if_exists=True)
    # Drop embedding columns
    op.drop_column("rag_document_chunks", "embedding")
    op.drop_column("rag_document_chunks", "embedding_model")
    op.drop_column("rag_document_chunks", "embedding_provider")


def downgrade() -> None:
    """Downgrade schema."""
    from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]

    op.add_column(
        "rag_document_chunks",
        sa.Column("embedding_provider", sa.String(length=50), nullable=False),
    )
    op.add_column(
        "rag_document_chunks",
        sa.Column("embedding_model", sa.String(length=100), nullable=False),
    )
    op.add_column(
        "rag_document_chunks",
        sa.Column("embedding", Vector(384), nullable=False),
    )
    op.create_index(
        "idx_rag_chunks_embedding_hnsw",
        "rag_document_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
