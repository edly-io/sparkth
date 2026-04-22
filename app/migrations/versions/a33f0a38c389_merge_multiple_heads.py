"""Merge multiple heads

Revision ID: a33f0a38c389
Revises: 2c9970b35fd1, g6d9f0b1c2d3
Create Date: 2026-04-14 18:14:02.936568

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a33f0a38c389"
down_revision: Union[str, Sequence[str], None] = ("2c9970b35fd1", "g6d9f0b1c2d3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
