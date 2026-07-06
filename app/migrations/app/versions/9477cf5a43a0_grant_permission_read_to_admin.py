"""grant permission.read to admin

Revision ID: 9477cf5a43a0
Revises: 86c94c01a092
Create Date: 2026-07-02 18:44:06.249675

Grants the ``permission.read`` permission to the seeded ``admin`` role, so existing admins
can list the assignable permission vocabulary (the role-management API's permission listing,
which is gated on ``permission.read``).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9477cf5a43a0"
down_revision: Union[str, Sequence[str], None] = "86c94c01a092"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal strings — a migration is a historical snapshot and must not import permission/role
# symbols (a later rename or removal would break replaying history).
_ROLE = "admin"
_PERMISSION = "permission.read"


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
