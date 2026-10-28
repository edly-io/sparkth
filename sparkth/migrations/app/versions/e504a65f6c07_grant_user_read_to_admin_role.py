"""grant user.read to admin role

Revision ID: e504a65f6c07
Revises: 942a21526c53
Create Date: 2026-10-21 12:30:00.000000

Grants the ``user.read`` permission to the seeded ``admin`` role, so existing admins
see usernames in analytics results.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e504a65f6c07"
down_revision: Union[str, Sequence[str], None] = "942a21526c53"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal strings — a migration is a historical snapshot and must not import permission/role symbols.
_ROLE = "admin"
_PERMISSION = "user.read"


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
