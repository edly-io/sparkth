"""merge migration heads

Revision ID: b5bf23a5f00e
Revises: 4aac177b2327, cd057b1ef056
Create Date: 2026-07-27 17:29:55.014067

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "b5bf23a5f00e"
down_revision: Union[str, Sequence[str], None] = ("4aac177b2327", "cd057b1ef056")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
