"""seed admin role and grant to existing superusers

Revision ID: b8bf876007e2
Revises: 7ee9891441d3
Create Date: 2026-06-18 16:32:36.226825

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8bf876007e2"
down_revision: Union[str, Sequence[str], None] = "7ee9891441d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal permission/role strings — a migration is a historical snapshot, so it must
# NOT import EmailWhitelistPermissions or ROLE_ADMIN (a future rename would break history).
_ROLE = "admin"
_PERMISSIONS = ("email.whitelist.read", "email.whitelist.create", "email.whitelist.delete")


def upgrade() -> None:
    conn = op.get_bind()
    role_id = conn.execute(
        sa.text(
            "INSERT INTO role (name, description, created_at, updated_at) "
            "VALUES (:name, 'Full administrative access', now(), now()) RETURNING id"
        ),
        {"name": _ROLE},
    ).scalar_one()
    for permission in _PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO role_permission (role_id, permission, created_at, updated_at) "
                "VALUES (:role_id, :permission, now(), now())"
            ),
            {"role_id": role_id, "permission": permission},
        )
    conn.execute(
        sa.text(
            "INSERT INTO role_assignment "
            "(user_id, role_id, scope_type, scope_id, is_deleted, created_at, updated_at) "
            "SELECT id, :role_id, :scope_type, NULL, false, now(), now() "
            'FROM "user" WHERE is_superuser = true AND is_deleted = false'
        ),
        {"role_id": role_id, "scope_type": "global"},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM role_assignment WHERE role_id IN (SELECT id FROM role WHERE name = :name)"),
        {"name": _ROLE},
    )
    conn.execute(
        sa.text("DELETE FROM role_permission WHERE role_id IN (SELECT id FROM role WHERE name = :name)"),
        {"name": _ROLE},
    )
    conn.execute(sa.text("DELETE FROM role WHERE name = :name"), {"name": _ROLE})
