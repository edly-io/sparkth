"""merge heads

Revision ID: 6bdd5691de9d
Revises: c49841c8bfbb, d300f558a4b4, f1e914de8460
Create Date: 2026-05-20 14:48:36.167708

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "6bdd5691de9d"
down_revision: Union[str, Sequence[str], None] = ("c49841c8bfbb", "d300f558a4b4", "f1e914de8460")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
