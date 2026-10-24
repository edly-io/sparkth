"""grant user.read to admin role

Revision ID: e504a65f6c07
Revises: b7c6b6b76764
Create Date: 2026-10-21 12:30:00.000000

Grants the ``user.read`` permission to the seeded ``admin`` role, so existing admins
see usernames in analytics results.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e504a65f6c07"
down_revision: Union[str, Sequence[str], None] = "b7c6b6b76764"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal strings — a migration is a historical snapshot and must not import permission/role symbols.
_ROLE = "admin"
_PERMISSION = "user.read"


def upgrade() -> None:
    conn = op.get_bind()
    # INSERT ... SELECT so it is a no-op when the admin role hasn't been seeded.
    conn.execute(
        sa.text(
            "INSERT INTO role_permission (role_id, permission, created_at, updated_at) "
            "SELECT id, :permission, now(), now() FROM role WHERE name = :role"
        ),
        {"permission": _PERMISSION, "role": _ROLE},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM role_permission WHERE permission = :permission "
            "AND role_id IN (SELECT id FROM role WHERE name = :role)"
        ),
        {"permission": _PERMISSION, "role": _ROLE},
    )
