"""merge heads

Revision ID: fa552d6ba726
Revises: 5ee564514b35, a1b2c3d4e5f6
Create Date: 2026-03-11 12:45:21.386099

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'fa552d6ba726'
down_revision: Union[str, Sequence[str], None] = ('5ee564514b35', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
