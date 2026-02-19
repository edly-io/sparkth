"""add is_error to chat_messages

Revision ID: 12ec22bbfa0d
Revises: 2154d6956f32
Create Date: 2026-02-21 22:07:51.468033

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '12ec22bbfa0d'
down_revision: Union[str, Sequence[str], None] = '2154d6956f32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('chat_messages', sa.Column('is_error', sa.Boolean(), nullable=False))
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chat_messages', 'is_error')
    # ### end Alembic commands ###
