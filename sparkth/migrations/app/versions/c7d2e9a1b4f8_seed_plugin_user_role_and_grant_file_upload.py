"""seed plugin_user role and grant file.upload to sparkth_user

Revision ID: c7d2e9a1b4f8
Revises: b46afd20018b
Create Date: 2026-11-16 10:00:00.000000

Seeds the built-in ``plugin_user`` role holding ``plugin.use`` and assigns it at ``global`` to every
existing account, so every account can use every plugin. It also grants ``file.upload`` to the
``sparkth_user`` role, so every account can upload files at its own ``user`` scope.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d2e9a1b4f8"
down_revision: Union[str, Sequence[str], None] = "b46afd20018b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal strings: a migration is a historical snapshot and must not import permission/role symbols.
_PLUGIN_ROLE = "plugin_user"
_PLUGIN_PERMISSION = "plugin.use"
_USER_ROLE = "sparkth_user"
_UPLOAD_PERMISSION = "file.upload"
_GLOBAL = "global"


def upgrade() -> None:
    conn = op.get_bind()
    role_id = conn.execute(
        sa.text(
            "INSERT INTO role (name, description, is_builtin, created_at, updated_at) "
            "VALUES (:name, 'Default role of every account, letting it use every plugin', true, now(), now()) "
            "RETURNING id"
        ),
        {"name": _PLUGIN_ROLE},
    ).scalar_one()
    conn.execute(
        sa.text(
            "INSERT INTO role_permission (role_id, permission, created_at, updated_at) "
            "VALUES (:role_id, :permission, now(), now())"
        ),
        {"role_id": role_id, "permission": _PLUGIN_PERMISSION},
    )
    conn.execute(
        sa.text(
            "INSERT INTO role_assignment "
            "(user_id, role_id, scope, scope_object_id, is_deleted, created_at, updated_at) "
            'SELECT id, :role_id, :scope, NULL, false, now(), now() FROM "user"'
        ),
        {"role_id": role_id, "scope": _GLOBAL},
    )
    # INSERT ... SELECT so it is a no-op when the role hasn't been seeded.
    conn.execute(
        sa.text(
            "INSERT INTO role_permission (role_id, permission, created_at, updated_at) "
            "SELECT id, :permission, now(), now() FROM role WHERE name = :role"
        ),
        {"permission": _UPLOAD_PERMISSION, "role": _USER_ROLE},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM role_permission WHERE permission = :permission "
            "AND role_id IN (SELECT id FROM role WHERE name = :role)"
        ),
        {"permission": _UPLOAD_PERMISSION, "role": _USER_ROLE},
    )
    for table in ("role_assignment", "group_role_assignment", "role_permission"):
        conn.execute(
            sa.text(f"DELETE FROM {table} WHERE role_id IN (SELECT id FROM role WHERE name = :name)"),
            {"name": _PLUGIN_ROLE},
        )
    conn.execute(sa.text("DELETE FROM role WHERE name = :name"), {"name": _PLUGIN_ROLE})
