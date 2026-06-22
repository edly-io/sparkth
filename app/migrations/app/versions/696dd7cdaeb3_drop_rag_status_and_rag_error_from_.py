"""drop rag_status and rag_error from drive_files

Revision ID: 696dd7cdaeb3
Revises: e65be7f91ab2
Create Date: 2026-06-08 13:12:37.931228

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "696dd7cdaeb3"
down_revision: Union[str, Sequence[str], None] = "e65be7f91ab2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop rag_status and rag_error columns from drive_files; drop old rag_drive_file_chunk_links table."""
    op.drop_table("rag_drive_file_chunk_links")
    op.drop_column("drive_files", "rag_error")
    op.drop_column("drive_files", "rag_status")


def downgrade() -> None:
    """Restore rag_status and rag_error columns to drive_files; recreate rag_drive_file_chunk_links table."""
    op.add_column(
        "drive_files",
        sa.Column(
            "rag_status",
            postgresql.ENUM("PROCESSING", "READY", "FAILED", "QUEUED", name="ragstatus"),
            autoincrement=False,
            nullable=True,
        ),
    )
    op.add_column("drive_files", sa.Column("rag_error", sa.VARCHAR(), autoincrement=False, nullable=True))
    op.create_table(
        "rag_drive_file_chunk_links",
        sa.Column("drive_file_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.Column("chunk_id", sa.INTEGER(), autoincrement=False, nullable=False),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["rag_document_chunks.id"],
            name=op.f("rag_drive_file_chunk_links_chunk_id_fkey"),
        ),
        sa.ForeignKeyConstraint(
            ["drive_file_id"],
            ["drive_files.id"],
            name=op.f("rag_drive_file_chunk_links_drive_file_id_fkey"),
        ),
        sa.PrimaryKeyConstraint("drive_file_id", "chunk_id", name=op.f("rag_drive_file_chunk_links_pkey")),
    )
