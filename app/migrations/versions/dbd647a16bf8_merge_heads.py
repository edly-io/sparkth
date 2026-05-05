"""merge heads

Revision ID: dbd647a16bf8
Revises: 5c3e0d64672c, e85d903dcb3b
Create Date: 2026-04-22 16:01:18.374177

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'dbd647a16bf8'
down_revision: Union[str, Sequence[str], None] = ('5c3e0d64672c', 'e85d903dcb3b')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
