"""add attachement metadata to Message

Revision ID: 53632e4b3fc3
Revises: 12ec22bbfa0d
Create Date: 2026-02-23 22:36:29.180689

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '53632e4b3fc3'
down_revision: Union[str, Sequence[str], None] = '12ec22bbfa0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "chat_messages",
        sa.Column(
            "message_type",
            sa.String(20),
            nullable=False,
            server_default="text",
        ),
    )
    op.add_column(
        "chat_messages",
        sa.Column("attachment_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "chat_messages",
        sa.Column("attachment_size", sa.Integer(), nullable=True),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("chat_messages", "attachment_size")
    op.drop_column("chat_messages", "attachment_name")
    op.drop_column("chat_messages", "message_type")
    # ### end Alembic commands ###
