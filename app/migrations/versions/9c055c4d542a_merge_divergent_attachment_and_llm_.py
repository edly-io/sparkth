"""merge divergent attachment and llm config migrations

Revision ID: 9c055c4d542a
Revises: e85d903dcb3b, ed5bc53f5b16
Create Date: 2026-04-25 06:21:08.812330

"""

from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = "9c055c4d542a"
down_revision: Union[str, Sequence[str], None] = ("e85d903dcb3b", "ed5bc53f5b16")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
