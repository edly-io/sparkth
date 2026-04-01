"""add_rag_pipeline_fields

Revision ID: c8f2d4a67e19
Revises: b7e3a1f29d04
Create Date: 2026-04-01 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8f2d4a67e19"
down_revision: Union[str, Sequence[str], None] = "b7e3a1f29d04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add RAG pipeline fields and bridge table."""
    # drive_files: RAG processing status and file content hash for duplicate detection
    op.add_column(
        "drive_files",
        sa.Column("rag_status", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
    )
    op.add_column(
        "drive_files",
        sa.Column("content_hash", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
    )

    # rag_document_chunks: SHA-256 hash of the chunk content
    op.add_column(
        "rag_document_chunks",
        sa.Column("chunk_content_hash", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
    )
    op.create_index(
        op.f("ix_rag_document_chunks_chunk_content_hash"),
        "rag_document_chunks",
        ["chunk_content_hash"],
        unique=False,
    )

    # Bridge table: many-to-many between drive_files and rag_document_chunks
    op.create_table(
        "rag_drive_file_chunk_links",
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
        sa.Column("drive_file_id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["drive_file_id"], ["drive_files.id"]),
        sa.ForeignKeyConstraint(["chunk_id"], ["rag_document_chunks.id"]),
        sa.PrimaryKeyConstraint("drive_file_id", "chunk_id"),
    )


def downgrade() -> None:
    """Remove RAG pipeline fields and bridge table."""
    op.drop_table("rag_drive_file_chunk_links")
    op.drop_index(op.f("ix_rag_document_chunks_chunk_content_hash"), table_name="rag_document_chunks")
    op.drop_column("rag_document_chunks", "chunk_content_hash")
    op.drop_column("drive_files", "content_hash")
    op.drop_column("drive_files", "rag_status")
