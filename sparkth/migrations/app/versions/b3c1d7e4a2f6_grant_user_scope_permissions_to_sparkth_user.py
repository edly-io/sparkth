"""grant the user-scope permissions to the sparkth_user role

Revision ID: b3c1d7e4a2f6
Revises: 9adb59c579d5
Create Date: 2026-11-13 10:00:00.000000

Grants the LLM configuration, Compose conversation and Google Drive permissions to the default
``sparkth_user`` role, so every account can manage its own records. It also assigns the role,
at the account's own ``user`` scope, to every account that never had it: code deployed before the
role existed can still create accounts after the first backfill ran. An account whose own assignment
was revoked (soft-deleted) stays without the role.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3c1d7e4a2f6"
down_revision: Union[str, Sequence[str], None] = "9adb59c579d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal strings: a migration is a historical snapshot and must not import permission/role
# symbols (a later rename or removal would break replaying history).
_ROLE = "sparkth_user"
_SCOPE = "user"
_PERMISSIONS = (
    "llm.config.create",
    "llm.config.read",
    "llm.config.update",
    "llm.config.delete",
    "compose.conversation.read",
    "compose.conversation.write",
    "googledrive.read",
    "googledrive.sync",
    "googledrive.delete",
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
    # Accounts that never had the role (any row, even soft-deleted, counts); a no-op without the role.
    conn.execute(
        sa.text(
            "INSERT INTO role_assignment "
            "(user_id, role_id, scope, scope_object_id, is_deleted, created_at, updated_at) "
            'SELECT u.id, r.id, :scope, CAST(u.id AS text), false, now(), now() FROM "user" u '
            "JOIN role r ON r.name = :role "
            "WHERE NOT EXISTS (SELECT 1 FROM role_assignment ra WHERE ra.user_id = u.id "
            "AND ra.role_id = r.id AND ra.scope = :scope "
            "AND ra.scope_object_id = CAST(u.id AS text))"
        ),
        {"role": _ROLE, "scope": _SCOPE},
    )


def downgrade() -> None:
    conn = op.get_bind()
    # The re-backfilled assignments stay: they cannot be told apart from backfilled or sign-up ones,
    # and the previous revision's downgrade removes them all.
    for permission in _PERMISSIONS:
        conn.execute(
            sa.text(
                "DELETE FROM role_permission WHERE permission = :permission "
                "AND role_id IN (SELECT id FROM role WHERE name = :role)"
            ),
            {"permission": permission, "role": _ROLE},
        )
