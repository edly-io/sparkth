"""merge migration heads

Revision ID: b7c6b6b76764
Revises: 5740224a9dd9, 98acc3e4d48a
Create Date: 2026-10-22 14:07:05.464961

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "b7c6b6b76764"
down_revision: Union[str, Sequence[str], None] = ("5740224a9dd9", "98acc3e4d48a")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
