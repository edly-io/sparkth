"""protect audit_events from update and delete

Revision ID: a282a83eec61
Revises: 0a2dfb2685ad
Create Date: 2026-09-16 14:51:28.965178

"""

from typing import Sequence, Union

from alembic import op

from sparkth.core.audit.models import APPEND_ONLY_DDL, APPEND_ONLY_DROP_DDL

# revision identifiers, used by Alembic.
revision: str = "a282a83eec61"
down_revision: Union[str, Sequence[str], None] = "0a2dfb2685ad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Install the triggers that reject UPDATE, DELETE, and TRUNCATE on audit_events.

    The statements are the same ones ``create_all`` attaches to the table for
    fresh databases; this migration installs them where the table already exists.
    """
    for statement in APPEND_ONLY_DDL[op.get_bind().dialect.name]:
        op.execute(statement)


def downgrade() -> None:
    """Remove the append-only triggers (the rows themselves are untouched)."""
    for statement in APPEND_ONLY_DROP_DDL[op.get_bind().dialect.name]:
        op.execute(statement)
