"""grant role assignment perms to admin

Revision ID: a5ef4de68044
Revises: 21a9ae1ebffd
Create Date: 2026-11-26 14:19:44.672567

Grants the role-assignment permissions (role.assign/revoke) to the seeded ``admin`` role, so
existing admins can give roles and take them away through the API.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5ef4de68044"
down_revision: Union[str, Sequence[str], None] = "21a9ae1ebffd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal strings — a migration is a historical snapshot and must not import permission/role
# symbols (a later rename or removal would break replaying history).
_ROLE = "admin"
_PERMISSIONS = ("role.assign", "role.revoke")


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
