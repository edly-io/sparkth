"""grant role-management perms to admin

Revision ID: 86c94c01a092
Revises: 3364c02e8569
Create Date: 2026-06-24 17:16:58.177720

Grants the role-management permissions (role.create/read/update/delete) to the seeded
``admin`` role, so existing admins can use the role-management API.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "86c94c01a092"
down_revision: Union[str, Sequence[str], None] = "3364c02e8569"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal strings — a migration is a historical snapshot and must not import permission/role
# symbols (a later rename or removal would break replaying history).
_ROLE = "admin"
_PERMISSIONS = ("role.create", "role.read", "role.update", "role.delete")


def upgrade() -> None:
    conn = op.get_bind()
    for permission in _PERMISSIONS:
        # INSERT ... SELECT so it is a no-op when the admin role hasn't been seeded.
        conn.execute(
            sa.text(
                "INSERT INTO role_permission (role_id, permission, created_at, updated_at) "
                "SELECT id, :permission, now(), now() FROM role WHERE name = :role"
            ),
            {"permission": permission, "role": _ROLE},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for permission in _PERMISSIONS:
        conn.execute(
            sa.text(
                "DELETE FROM role_permission WHERE permission = :permission "
                "AND role_id IN (SELECT id FROM role WHERE name = :role)"
            ),
            {"permission": permission, "role": _ROLE},
        )
