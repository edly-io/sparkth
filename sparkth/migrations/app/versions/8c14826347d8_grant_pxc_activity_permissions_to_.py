"""grant pxc activity permissions to sparkth_user

Revision ID: 8c14826347d8
Revises: 233eacc2996e
Create Date: 2026-11-24 14:54:33.717352

Grants the four PXC activity permissions (read, update, delete, place) to the default ``sparkth_user``
role. Every account holds that role at its own ``user`` scope, and the permissions are checked at the
``user`` scope of an activity's owner, so every account keeps access to its own activities. A deployment
without the role gets no rows.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8c14826347d8"
down_revision: Union[str, Sequence[str], None] = "233eacc2996e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal strings: a migration is a historical snapshot and must not import permission/role
# symbols (a later rename or removal would break replaying history).
_ROLE = "sparkth_user"
_PERMISSIONS = (
    "pxc.activity.read",
    "pxc.activity.update",
    "pxc.activity.delete",
    "pxc.activity.place",
)


def upgrade() -> None:
    conn = op.get_bind()
    for permission in _PERMISSIONS:
        # INSERT ... SELECT so it is a no-op when the role hasn't been seeded.
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
