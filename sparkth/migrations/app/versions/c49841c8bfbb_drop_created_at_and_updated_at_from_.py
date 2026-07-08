"""drop created_at and updated_at from chat_conversation_attachments

Revision ID: c49841c8bfbb
Revises: 87e049122b83
Create Date: 2026-05-15 15:03:37.500001

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c49841c8bfbb"
down_revision: Union[str, Sequence[str], None] = "87e049122b83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("chat_conversation_attachments", "created_at")
    op.drop_column("chat_conversation_attachments", "updated_at")


def downgrade() -> None:
    op.add_column(
        "chat_conversation_attachments",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "chat_conversation_attachments",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
