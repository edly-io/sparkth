"""merge migration heads after main merge

Revision ID: f0dcdf4b2d63
Revises: c49841c8bfbb, f1e914de8460
Create Date: 2026-05-19 15:16:12.708768

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "f0dcdf4b2d63"
down_revision: Union[str, Sequence[str], None] = ("c49841c8bfbb", "f1e914de8460")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
