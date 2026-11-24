"""grant plugin.manage to admin role

Revision ID: 233eacc2996e
Revises: a5b4a01a31ca
Create Date: 2026-11-24 14:56:00.294906

Grants the ``plugin.manage`` permission to the seeded ``admin`` role, so existing admins
can switch a plugin on or off for everyone.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "233eacc2996e"
down_revision: Union[str, Sequence[str], None] = "a5b4a01a31ca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal strings — a migration is a historical snapshot and must not import permission/role symbols.
_ROLE = "admin"
_PERMISSION = "plugin.manage"


_role = sa.table("role", sa.column("id"), sa.column("name"))
_role_permission = sa.table(
    "role_permission",
    sa.column("role_id"),
    sa.column("permission"),
    sa.column("created_at"),
    sa.column("updated_at"),
)


def upgrade() -> None:
    # INSERT ... SELECT so it is a no-op when the admin role hasn't been seeded.
    admin = sa.select(_role.c.id, sa.literal(_PERMISSION), sa.func.now(), sa.func.now()).where(_role.c.name == _ROLE)
    op.execute(_role_permission.insert().from_select(["role_id", "permission", "created_at", "updated_at"], admin))


def downgrade() -> None:
    admin_ids = sa.select(_role.c.id).where(_role.c.name == _ROLE)
    op.execute(
        _role_permission.delete().where(
            _role_permission.c.permission == _PERMISSION, _role_permission.c.role_id.in_(admin_ids)
        )
    )
