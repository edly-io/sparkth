"""merge whitelist migration with existing heads

Revision ID: 2c169295972a
Revises: 2899d4e35c26, e85d903dcb3b, ed5bc53f5b16
Create Date: 2026-04-27 16:30:26.373816

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "2c169295972a"
down_revision: Union[str, Sequence[str], None] = ("2899d4e35c26", "e85d903dcb3b", "ed5bc53f5b16")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
