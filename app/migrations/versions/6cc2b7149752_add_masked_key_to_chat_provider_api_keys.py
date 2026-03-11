"""add masked_key to chat_provider_api_keys

Revision ID: 6cc2b7149752
Revises: 53632e4b3fc3
Create Date: 2026-03-03 15:34:00.470860

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '6cc2b7149752'
down_revision: Union[str, Sequence[str], None] = '53632e4b3fc3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_provider_api_keys",
        sa.Column("masked_key", sa.Text(), nullable=False, server_default="****"),
    )
    op.alter_column("chat_provider_api_keys", "masked_key", server_default=None)


def downgrade() -> None:
    op.drop_column("chat_provider_api_keys", "masked_key")