"""merge migration heads

Revision ID: b927c4f42aff
Revises: 3364c02e8569, 4c98e624d8c7
Create Date: 2026-06-18 19:40:55.891799

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "b927c4f42aff"
down_revision: Union[str, Sequence[str], None] = ("3364c02e8569", "4c98e624d8c7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
