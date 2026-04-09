"""merge heads

Revision ID: 2c9970b35fd1
Revises: b7e3a1f29d04, b9f1c2d3e4a5
Create Date: 2026-04-07 20:05:25.874682

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '2c9970b35fd1'
down_revision: Union[str, Sequence[str], None] = ('b7e3a1f29d04', 'b9f1c2d3e4a5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
