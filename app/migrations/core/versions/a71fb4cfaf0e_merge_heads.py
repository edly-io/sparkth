"""merge heads

Revision ID: a71fb4cfaf0e
Revises: 2c9970b35fd1, g6d9f0b1c2d3
Create Date: 2026-04-10 15:24:55.490864

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "a71fb4cfaf0e"
down_revision: Union[str, Sequence[str], None] = ("2c9970b35fd1", "g6d9f0b1c2d3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
