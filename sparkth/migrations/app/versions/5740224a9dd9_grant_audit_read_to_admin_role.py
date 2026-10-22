"""grant audit.read to admin role

Revision ID: 5740224a9dd9
Revises: 72c7ac343c02
Create Date: 2026-10-19 17:59:18.362014

Grants the ``audit.read`` permission to the seeded ``admin`` role, so existing admins
can query and export the audit trail (``/api/v1/audit``).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5740224a9dd9"
down_revision: Union[str, Sequence[str], None] = "72c7ac343c02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal strings: a migration is a historical snapshot and must not import permission/role
# symbols (a later rename or removal would break replaying history).
_ROLE = "admin"
_PERMISSION = "audit.read"


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
