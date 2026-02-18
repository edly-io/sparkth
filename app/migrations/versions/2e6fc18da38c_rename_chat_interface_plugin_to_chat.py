"""rename_chat_interface_plugin_to_chat

Revision ID: 2e6fc18da38c
Revises: 2154d6956f32
Create Date: 2026-02-20 14:37:55.363455

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '2e6fc18da38c'
down_revision: Union[str, Sequence[str], None] = '2154d6956f32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("""
        UPDATE plugins
        SET name = 'chat'
        WHERE name = 'chat_interface'
    """)


def downgrade():
    op.execute("""
        UPDATE plugins
        SET name = 'chat_interface'
        WHERE name = 'chat'
    """)