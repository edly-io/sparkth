"""assign plugin_user to accounts that never had it

Revision ID: d4e8a1b6c3f9
Revises: c7d2e9a1b4f8
Create Date: 2026-11-16 12:00:00.000000

Assigns the ``plugin_user`` role at ``global`` to every account with no ``plugin_user`` assignment at all,
so accounts created while a deploy was rolling out can use plugins. An account whose assignment was
revoked (soft-deleted) stays without the role. The downgrade is a no-op: the added assignments cannot be
told apart from sign-up ones, and removing the role is the previous revision's downgrade.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e8a1b6c3f9"
down_revision: Union[str, Sequence[str], None] = "c7d2e9a1b4f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal strings: a migration is a historical snapshot and must not import permission/role symbols.
_ROLE = "plugin_user"
_GLOBAL = "global"


def upgrade() -> None:
    # Any row, even soft-deleted, counts as existing; a no-op when the role is not seeded.
    op.get_bind().execute(
        sa.text(
            "INSERT INTO role_assignment "
            "(user_id, role_id, scope, scope_object_id, is_deleted, created_at, updated_at) "
            'SELECT u.id, r.id, :scope, NULL, false, now(), now() FROM "user" u '
            "JOIN role r ON r.name = :role "
            "WHERE NOT EXISTS (SELECT 1 FROM role_assignment ra WHERE ra.user_id = u.id AND ra.role_id = r.id)"
        ),
        {"role": _ROLE, "scope": _GLOBAL},
    )


def downgrade() -> None:
    pass
