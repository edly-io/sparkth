"""grant pxc play and edit to sparkth_user

Revision ID: f4f3ab101db9
Revises: 8c14826347d8
Create Date: 2026-11-26 22:50:00.000000

Grants ``pxc.activity.play`` and ``pxc.activity.edit`` to the default ``sparkth_user`` role. Every account
holds that role at its own ``user`` scope, so every account can open its own activities at either level. A
deployment without the role gets no rows.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4f3ab101db9"
down_revision: Union[str, Sequence[str], None] = "8c14826347d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal strings: a migration is a historical snapshot and must not import permission/role
# symbols (a later rename or removal would break replaying history).
_ROLE = "sparkth_user"
_PERMISSIONS = (
    "pxc.activity.play",
    "pxc.activity.edit",
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
