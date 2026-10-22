"""merge migration heads

Revision ID: 98acc3e4d48a
Revises: 51c82933dce3, ca02295ab4e4
Create Date: 2026-10-22 13:54:56.158676

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "98acc3e4d48a"
down_revision: Union[str, Sequence[str], None] = ("51c82933dce3", "ca02295ab4e4")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
