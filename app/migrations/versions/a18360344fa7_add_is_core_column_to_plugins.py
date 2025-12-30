"""Add is_core column to plugins

Revision ID: a18360344fa7
Revises: 493e7a1bfb65
Create Date: 2025-12-18 19:07:21.110094

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a18360344fa7'
down_revision: Union[str, Sequence[str], None] = '493e7a1bfb65'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('plugins', sa.Column('is_core', sa.Boolean(), nullable=False))
    op.add_column('plugins', sa.Column('config_schema', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('plugins', 'config_schema')
    op.drop_column('plugins', 'is_core')
