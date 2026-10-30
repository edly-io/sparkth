"""add deletable to role

Revision ID: ab88a9f7556e
Revises: fd29c3a6164d
Create Date: 2026-10-30 13:01:11.799171

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ab88a9f7556e"
down_revision: Union[str, Sequence[str], None] = "fd29c3a6164d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SHIPPED_ROLES = ("admin",)


def upgrade() -> None:
    """Add role.deletable and mark the shipped roles non-deletable."""
    op.add_column("role", sa.Column("deletable", sa.Boolean(), server_default=sa.true(), nullable=False))
    for name in _SHIPPED_ROLES:
        op.execute(sa.text("UPDATE role SET deletable = false WHERE name = :name").bindparams(name=name))


def downgrade() -> None:
    """Drop role.deletable."""
    op.drop_column("role", "deletable")
