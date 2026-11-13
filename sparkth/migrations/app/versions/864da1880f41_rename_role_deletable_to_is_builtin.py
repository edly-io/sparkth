"""rename role deletable to is_builtin

Revision ID: 864da1880f41
Revises: b3c1d7e4a2f6
Create Date: 2026-11-13 14:41:08.737608

Renames ``role.deletable`` to ``role.is_builtin`` and flips its meaning: true for a role shipped
with Sparkth, false (the new server default) for a role an operator creates.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "864da1880f41"
down_revision: Union[str, Sequence[str], None] = "b3c1d7e4a2f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename role.deletable to role.is_builtin, flip the stored values and default to false."""
    op.alter_column("role", "deletable", new_column_name="is_builtin")
    op.execute("UPDATE role SET is_builtin = NOT is_builtin")
    op.alter_column("role", "is_builtin", server_default=sa.false())


def downgrade() -> None:
    """Rename role.is_builtin back to role.deletable, flip the stored values and default to true."""
    op.alter_column("role", "is_builtin", server_default=sa.true())
    op.execute("UPDATE role SET is_builtin = NOT is_builtin")
    op.alter_column("role", "is_builtin", new_column_name="deletable")
