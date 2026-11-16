"""Add an indexed parent_scope_path to compose conversations.

Existing conversations are backfilled with their owner's user scope path.
"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "912a627eff27"
down_revision: Union[str, Sequence[str], None] = "864da1880f41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the column and its index, then fill every existing row."""
    op.add_column(
        "compose_conversations",
        sa.Column("parent_scope_path", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index(
        op.f("ix_compose_conversations_parent_scope_path"),
        "compose_conversations",
        ["parent_scope_path"],
        unique=False,
    )
    op.execute("UPDATE compose_conversations SET parent_scope_path = 'user:' || user_id")


def downgrade() -> None:
    """Drop the index, then the column."""
    op.drop_index(op.f("ix_compose_conversations_parent_scope_path"), table_name="compose_conversations")
    op.drop_column("compose_conversations", "parent_scope_path")
