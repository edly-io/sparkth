"""merge migration heads

Revision ID: e3e4722fe6a0
Revises: 5174eca74b5e, 696dd7cdaeb3
Create Date: 2026-06-10 16:19:04.670551

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "e3e4722fe6a0"
down_revision: Union[str, Sequence[str], None] = ("5174eca74b5e", "696dd7cdaeb3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
