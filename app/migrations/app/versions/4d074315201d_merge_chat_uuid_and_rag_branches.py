"""merge_chat_uuid_and_rag_branches

Revision ID: 4d074315201d
Revises: b9f1c2d3e4a5, e1f2a3b4c5d6
Create Date: 2026-04-08 00:33:46.512518

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "4d074315201d"
down_revision: Union[str, Sequence[str], None] = ("b9f1c2d3e4a5", "e1f2a3b4c5d6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
