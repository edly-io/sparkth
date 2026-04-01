"""add_uuid_to_chat_conversations

Revision ID: b9f1c2d3e4a5
Revises: fa552d6ba726
Create Date: 2026-04-01 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from uuid6 import uuid7

# revision identifiers, used by Alembic.
revision: str = "b9f1c2d3e4a5"
down_revision: Union[str, Sequence[str], None] = "fa552d6ba726"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_conversations", sa.Column("uuid", sa.Uuid(), nullable=True))

    # Backfill existing rows
    conn = op.get_bind()
    conversations = conn.execute(sa.text("SELECT id FROM chat_conversations")).fetchall()
    for row in conversations:
        conn.execute(
            sa.text("UPDATE chat_conversations SET uuid = :uuid WHERE id = :id"),
            {"uuid": str(uuid7()), "id": row[0]},
        )

    op.alter_column("chat_conversations", "uuid", nullable=False)
    op.create_index("idx_conversation_uuid", "chat_conversations", ["uuid"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_conversation_uuid", table_name="chat_conversations")
    op.drop_column("chat_conversations", "uuid")
