"""add active_drive_file_id to conversations

Revision ID: e85d903dcb3b
Revises: i2b3c4d5e6f7
Create Date: 2026-04-17 18:15:48.600130

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e85d903dcb3b"
down_revision: Union[str, Sequence[str], None] = "i2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("chat_conversations", sa.Column("active_drive_file_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_chat_conversations_active_drive_file_id"), "chat_conversations", ["active_drive_file_id"], unique=False
    )
    op.create_foreign_key(
        None, "chat_conversations", "drive_files", ["active_drive_file_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(None, "chat_conversations", type_="foreignkey")
    op.drop_index(op.f("ix_chat_conversations_active_drive_file_id"), table_name="chat_conversations")
    op.drop_column("chat_conversations", "active_drive_file_id")
