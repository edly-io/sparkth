"""extend responsetype enum with per-failure values

Revision ID: 2b8cd7530d90
Revises: 6bdd5691de9d
Create Date: 2026-05-20 16:06:15.303981

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2b8cd7530d90"
down_revision: Union[str, Sequence[str], None] = "6bdd5691de9d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE responsetype ADD VALUE IF NOT EXISTS 'no_files_resolved'")
        op.execute("ALTER TYPE responsetype ADD VALUE IF NOT EXISTS 'rag_not_ready'")
        op.execute("ALTER TYPE responsetype ADD VALUE IF NOT EXISTS 'drive_file_not_found'")
        op.execute("ALTER TYPE responsetype ADD VALUE IF NOT EXISTS 'retrieval_error'")


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQL does not support removing enum values
    pass
