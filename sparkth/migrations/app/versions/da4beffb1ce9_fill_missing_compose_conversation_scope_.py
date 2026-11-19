"""Fill missing compose conversation scope paths.

Conversations with no parent_scope_path get their owner's user scope path.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "da4beffb1ce9"
down_revision: Union[str, Sequence[str], None] = "912a627eff27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Set the owner's user scope path on every conversation that has none."""
    op.execute(
        "UPDATE compose_conversations SET parent_scope_path = 'user:' || user_id WHERE parent_scope_path IS NULL"
    )


def downgrade() -> None:
    """Do nothing: a filled scope path is left in place."""
