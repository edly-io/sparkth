"""merge whitelist with multi-attachment heads

Revision ID: 9566994a20ee
Revises: 2c169295972a, 3623a8f30805, 679e83f6c153
Create Date: 2026-04-28 17:53:29.063224

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "9566994a20ee"
down_revision: Union[str, Sequence[str], None] = ("2c169295972a", "3623a8f30805", "679e83f6c153")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
