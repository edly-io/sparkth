"""merge migration heads

Revision ID: 4c98e624d8c7
Revises: b8bf876007e2, d7fc891901e7
Create Date: 2026-06-18 19:36:31.161894

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "4c98e624d8c7"
down_revision: Union[str, Sequence[str], None] = ("b8bf876007e2", "d7fc891901e7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
