"""merge migration heads after main re-merge

Revision ID: 164908f2fa97
Revises: 6bdd5691de9d, f0dcdf4b2d63
Create Date: 2026-05-21 01:56:57.081051

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "164908f2fa97"
down_revision: Union[str, Sequence[str], None] = ("6bdd5691de9d", "f0dcdf4b2d63")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
