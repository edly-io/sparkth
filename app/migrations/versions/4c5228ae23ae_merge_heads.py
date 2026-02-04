"""merge heads

Revision ID: 4c5228ae23ae
Revises: 4381dd879570, d3e5f7a91b84
Create Date: 2026-02-04 19:37:55.539615

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '4c5228ae23ae'
down_revision: Union[str, Sequence[str], None] = ('4381dd879570', 'd3e5f7a91b84')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
