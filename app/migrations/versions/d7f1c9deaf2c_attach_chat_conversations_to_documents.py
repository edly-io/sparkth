"""attach chat conversations to documents

Revision ID: d7f1c9deaf2c
Revises: e3e4722fe6a0
Create Date: 2026-06-10 16:43:33.616390

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7f1c9deaf2c"
down_revision: Union[str, Sequence[str], None] = "e3e4722fe6a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "chat_conversation_attachments",
        sa.Column("document_id", sa.Integer(), nullable=True),
    )

    attachments = sa.table(
        "chat_conversation_attachments",
        sa.column("id", sa.Integer()),
        sa.column("conversation_id", sa.Integer()),
        sa.column("drive_file_id", sa.Integer()),
        sa.column("document_id", sa.Integer()),
    )
    drive_files = sa.table(
        "drive_files",
        sa.column("id", sa.Integer()),
        sa.column("document_id", sa.Integer()),
    )
    connection = op.get_bind()
    document_id_subquery = (
        sa.select(drive_files.c.document_id).where(drive_files.c.id == attachments.c.drive_file_id).scalar_subquery()
    )
    connection.execute(attachments.update().values(document_id=document_id_subquery))
    connection.execute(attachments.delete().where(attachments.c.document_id.is_(None)))

    retained_attachment_ids = (
        sa.select(sa.func.min(attachments.c.id))
        .where(attachments.c.document_id.isnot(None))
        .group_by(attachments.c.conversation_id, attachments.c.document_id)
    )
    connection.execute(attachments.delete().where(attachments.c.id.not_in(retained_attachment_ids)))

    op.alter_column(
        "chat_conversation_attachments",
        "document_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_index(op.f("idx_conv_attach_drive_file"), table_name="chat_conversation_attachments")
    op.drop_constraint(
        op.f("uq_conv_attachment"),
        "chat_conversation_attachments",
        type_="unique",
    )
    op.create_index(
        "idx_conv_attach_document",
        "chat_conversation_attachments",
        ["document_id"],
        unique=False,
    )
    op.create_unique_constraint(
        "uq_conv_document_attachment",
        "chat_conversation_attachments",
        ["conversation_id", "document_id"],
    )
    op.drop_constraint(
        op.f("chat_conversation_attachments_drive_file_id_fkey"),
        "chat_conversation_attachments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "chat_conversation_attachments_document_id_fkey",
        "chat_conversation_attachments",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_column("chat_conversation_attachments", "drive_file_id")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "chat_conversation_attachments",
        sa.Column("drive_file_id", sa.INTEGER(), autoincrement=False, nullable=True),
    )

    attachments = sa.table(
        "chat_conversation_attachments",
        sa.column("id", sa.Integer()),
        sa.column("document_id", sa.Integer()),
        sa.column("drive_file_id", sa.Integer()),
    )
    drive_files = sa.table(
        "drive_files",
        sa.column("id", sa.Integer()),
        sa.column("document_id", sa.Integer()),
    )
    connection = op.get_bind()
    drive_file_id_subquery = (
        sa.select(drive_files.c.id)
        .where(drive_files.c.document_id == attachments.c.document_id)
        .order_by(drive_files.c.id)
        .limit(1)
        .scalar_subquery()
    )
    connection.execute(attachments.update().values(drive_file_id=drive_file_id_subquery))
    connection.execute(attachments.delete().where(attachments.c.drive_file_id.is_(None)))

    op.alter_column(
        "chat_conversation_attachments",
        "drive_file_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_constraint(
        "chat_conversation_attachments_document_id_fkey",
        "chat_conversation_attachments",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("chat_conversation_attachments_drive_file_id_fkey"),
        "chat_conversation_attachments",
        "drive_files",
        ["drive_file_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "uq_conv_document_attachment",
        "chat_conversation_attachments",
        type_="unique",
    )
    op.drop_index("idx_conv_attach_document", table_name="chat_conversation_attachments")
    op.create_unique_constraint(
        op.f("uq_conv_attachment"),
        "chat_conversation_attachments",
        ["conversation_id", "drive_file_id"],
        postgresql_nulls_not_distinct=False,
    )
    op.create_index(
        op.f("idx_conv_attach_drive_file"),
        "chat_conversation_attachments",
        ["drive_file_id"],
        unique=False,
    )
    op.drop_column("chat_conversation_attachments", "document_id")
