"""add deletable to role

Revision ID: ab88a9f7556e
Revises: 84eeee1d97b9
Create Date: 2026-10-30 13:01:11.799171

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ab88a9f7556e"
down_revision: Union[str, Sequence[str], None] = "84eeee1d97b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SHIPPED_ROLES = ("admin",)


def upgrade() -> None:
    """Add role.deletable and mark the shipped roles non-deletable."""
    op.add_column("role", sa.Column("deletable", sa.Boolean(), server_default=sa.true(), nullable=False))
    role = sa.table("role", sa.column("name", sa.String), sa.column("deletable", sa.Boolean))
    op.execute(role.update().where(role.c.name.in_(_SHIPPED_ROLES)).values(deletable=False))


def downgrade() -> None:
    """Drop role.deletable."""
    op.drop_column("role", "deletable")
