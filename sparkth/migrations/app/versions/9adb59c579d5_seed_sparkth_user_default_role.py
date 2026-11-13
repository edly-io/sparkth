"""seed sparkth_user default role

Revision ID: 9adb59c579d5
Revises: ab88a9f7556e
Create Date: 2026-11-13 11:08:09.272482

Seeds the non-deletable ``sparkth_user`` role and assigns it to every existing account at that
account's own ``user`` scope. New accounts get the same assignment when they are created.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9adb59c579d5"
down_revision: Union[str, Sequence[str], None] = "ab88a9f7556e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal strings: a migration is a historical snapshot and must not import permission/role symbols.
_ROLE = "sparkth_user"
_SCOPE = "user"


def upgrade() -> None:
    conn = op.get_bind()
    role_id = conn.execute(
        sa.text(
            "INSERT INTO role (name, description, deletable, created_at, updated_at) "
            "VALUES (:name, 'Default role of every account, at its own user scope', false, now(), now()) "
            "RETURNING id"
        ),
        {"name": _ROLE},
    ).scalar_one()
    conn.execute(
        sa.text(
            "INSERT INTO role_assignment "
            "(user_id, role_id, scope, scope_object_id, is_deleted, created_at, updated_at) "
            'SELECT id, :role_id, :scope, CAST(id AS text), false, now(), now() FROM "user"'
        ),
        {"role_id": role_id, "scope": _SCOPE},
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
