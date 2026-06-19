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


drive_files = sa.table(
    "drive_files",
    sa.column("id", sa.Integer),
    sa.column("user_id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("mime_type", sa.String),
    sa.column("rag_status", sa.String),
    sa.column("rag_error", sa.String),
    sa.column("is_deleted", sa.Boolean),
    sa.column("deleted_at", sa.DateTime(timezone=True)),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
    sa.column("document_id", sa.Integer),
)

documents = sa.table(
    "documents",
    sa.column("id", sa.Integer),
    sa.column("user_id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("mime_type", sa.String),
    sa.column("status", sa.String),
    sa.column("error", sa.String),
    sa.column("is_deleted", sa.Boolean),
    sa.column("deleted_at", sa.DateTime(timezone=True)),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

rag_drive_file_chunk_links = sa.table(
    "rag_drive_file_chunk_links",
    sa.column("drive_file_id", sa.Integer),
    sa.column("chunk_id", sa.Integer),
)

rag_document_chunk_links = sa.table(
    "rag_document_chunk_links",
    sa.column("document_id", sa.Integer),
    sa.column("chunk_id", sa.Integer),
)


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
    connection = op.get_bind()
    connection.execute(
        sa.insert(documents).from_select(
            [
                "user_id",
                "name",
                "mime_type",
                "status",
                "error",
                "is_deleted",
                "deleted_at",
                "created_at",
                "updated_at",
            ],
            sa.select(
                drive_files.c.user_id,
                drive_files.c.name,
                drive_files.c.mime_type,
                sa.func.lower(sa.cast(drive_files.c.rag_status, sa.String())),
                drive_files.c.rag_error,
                drive_files.c.is_deleted,
                drive_files.c.deleted_at,
                drive_files.c.created_at,
                drive_files.c.updated_at,
            ).where(drive_files.c.rag_status.is_not(None)),
        )
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
    matching_document_id = (
        sa.select(documents.c.id)
        .where(
            documents.c.user_id == drive_files.c.user_id,
            documents.c.name == drive_files.c.name,
            documents.c.created_at == drive_files.c.created_at,
        )
        .limit(1)
        .scalar_subquery()
    )
    matching_document_exists = sa.exists().where(
        documents.c.user_id == drive_files.c.user_id,
        documents.c.name == drive_files.c.name,
        documents.c.created_at == drive_files.c.created_at,
    )
    connection.execute(sa.update(drive_files).where(matching_document_exists).values(document_id=matching_document_id))

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
    connection.execute(
        sa.insert(rag_document_chunk_links).from_select(
            ["document_id", "chunk_id"],
            sa.select(
                drive_files.c.document_id,
                rag_drive_file_chunk_links.c.chunk_id,
            )
            .join(rag_drive_file_chunk_links, drive_files.c.id == rag_drive_file_chunk_links.c.drive_file_id)
            .where(drive_files.c.document_id.is_not(None))
            .distinct(),
        )
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
