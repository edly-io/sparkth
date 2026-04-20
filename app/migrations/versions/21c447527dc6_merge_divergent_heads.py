"""merge divergent heads

Revision ID: 21c447527dc6
Revises: 5ae910dbda5d, i2b3c4d5e6f7
Create Date: 2026-04-20 12:30:28.004387

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "21c447527dc6"
down_revision: Union[str, Sequence[str], None] = ("5ae910dbda5d", "i2b3c4d5e6f7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
