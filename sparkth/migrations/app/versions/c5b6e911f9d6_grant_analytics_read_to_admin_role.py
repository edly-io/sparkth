"""grant analytics.read to admin role

Revision ID: c5b6e911f9d6
Revises: 50d919e8098c
Create Date: 2026-07-08 11:57:53.757960

Grants the ``analytics.read`` permission to the seeded ``admin`` role, so existing admins
can reach the in-app analytics dashboards / read API (gated on ``analytics.read``).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5b6e911f9d6"
down_revision: Union[str, Sequence[str], None] = "50d919e8098c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal strings — a migration is a historical snapshot and must not import permission/role
# symbols (a later rename or removal would break replaying history).
_ROLE = "admin"
_PERMISSION = "analytics.read"


def upgrade() -> None:
    conn = op.get_bind()
    # INSERT ... SELECT so it is a no-op when the admin role hasn't been seeded.
    conn.execute(
        sa.text(
            "INSERT INTO role_permission (role_id, permission, created_at, updated_at) "
            "SELECT id, :permission, now(), now() FROM role WHERE name = :role"
        ),
        {"permission": _PERMISSION, "role": _ROLE},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM role_permission WHERE permission = :permission "
            "AND role_id IN (SELECT id FROM role WHERE name = :role)"
        ),
        {"permission": _PERMISSION, "role": _ROLE},
    )
