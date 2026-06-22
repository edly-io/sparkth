"""extend responsetype enum with per-failure values

Revision ID: 8fc79cca199a
Revises: 164908f2fa97
Create Date: 2026-05-22 18:12:13.593282

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8fc79cca199a"
down_revision: Union[str, Sequence[str], None] = "164908f2fa97"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE responsetype ADD VALUE IF NOT EXISTS 'no_files_resolved'")
        op.execute("ALTER TYPE responsetype ADD VALUE IF NOT EXISTS 'rag_not_ready'")
        op.execute("ALTER TYPE responsetype ADD VALUE IF NOT EXISTS 'drive_file_not_found'")
        op.execute("ALTER TYPE responsetype ADD VALUE IF NOT EXISTS 'retrieval_error'")
    pass
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    pass
    # ### end Alembic commands ###
