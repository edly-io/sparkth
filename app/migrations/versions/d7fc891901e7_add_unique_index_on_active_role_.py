"""add unique index on active role assignments

Revision ID: d7fc891901e7
Revises: 7ee9891441d3
Create Date: 2026-06-18 19:17:56.265393

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7fc891901e7"
down_revision: Union[str, Sequence[str], None] = "7ee9891441d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "uq_role_assignment_active",
        "role_assignment",
        ["user_id", "role_id", "scope_type", sa.text("coalesce(scope_id, '')")],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        sqlite_where=sa.text("is_deleted = 0"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_role_assignment_active", table_name="role_assignment")
