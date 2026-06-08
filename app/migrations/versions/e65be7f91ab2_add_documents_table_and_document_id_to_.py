"""add documents table and document_id to drive_files

Revision ID: e65be7f91ab2
Revises: 8caaf9fdbce0
Create Date: 2026-06-08 08:37:41.476866

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e65be7f91ab2"
down_revision: Union[str, Sequence[str], None] = "8caaf9fdbce0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create documents table
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_user_id", "documents", ["user_id"])
    op.create_index("ix_documents_is_deleted", "documents", ["is_deleted"])

    # 2. Backfill: one Document row per DriveFile with a non-null rag_status.
    # Cast rag_status enum to text so it stores cleanly into documents.status (varchar).
    op.execute(
        """
        INSERT INTO documents (user_id, name, mime_type, status, error, is_deleted,
                               deleted_at, created_at, updated_at)
        SELECT user_id, name, mime_type,
               LOWER(rag_status::text),
               rag_error,
               is_deleted,
               deleted_at,
               created_at,
               updated_at
        FROM drive_files
        WHERE rag_status IS NOT NULL
        """
    )

    # 3. Add document_id to drive_files, populate from backfill
    op.add_column("drive_files", sa.Column("document_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_drive_files_document_id",
        "drive_files",
        "documents",
        ["document_id"],
        ["id"],
    )
    op.create_index("ix_drive_files_document_id", "drive_files", ["document_id"])

    # Populate document_id on drive_files by matching the backfill.
    # Uses subquery form for SQLite compatibility (tests run on SQLite).
    op.execute(
        """
        UPDATE drive_files
        SET document_id = (
            SELECT d.id FROM documents d
            WHERE d.user_id = drive_files.user_id
              AND d.name = drive_files.name
              AND d.created_at = drive_files.created_at
            LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1 FROM documents d
            WHERE d.user_id = drive_files.user_id
              AND d.name = drive_files.name
              AND d.created_at = drive_files.created_at
        )
        """
    )

    # 4. Create new rag_document_chunk_links table (FK -> documents.id)
    op.create_table(
        "rag_document_chunk_links",
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["chunk_id"], ["rag_document_chunks.id"]),
        sa.PrimaryKeyConstraint("document_id", "chunk_id"),
    )

    # 5. Backfill rag_document_chunk_links from rag_drive_file_chunk_links
    op.execute(
        """
        INSERT INTO rag_document_chunk_links (document_id, chunk_id)
        SELECT df.document_id, old.chunk_id
        FROM rag_drive_file_chunk_links old
        JOIN drive_files df ON df.id = old.drive_file_id
        WHERE df.document_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("rag_document_chunk_links")
    op.drop_constraint("fk_drive_files_document_id", "drive_files", type_="foreignkey")
    op.drop_index("ix_drive_files_document_id", table_name="drive_files")
    op.drop_column("drive_files", "document_id")
    op.drop_index("ix_documents_is_deleted", table_name="documents")
    op.drop_index("ix_documents_user_id", table_name="documents")
    op.drop_table("documents")
