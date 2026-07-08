"""merge migration heads

Revision ID: 29952e6a4b1b
Revises: 3fafda1c666e, c5b6e911f9d6
Create Date: 2026-07-13 13:46:12.174783

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "29952e6a4b1b"
down_revision: Union[str, Sequence[str], None] = ("3fafda1c666e", "c5b6e911f9d6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
