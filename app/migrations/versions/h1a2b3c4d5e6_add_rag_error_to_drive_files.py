"""add_rag_error_to_drive_files

Revision ID: h1a2b3c4d5e6
Revises: a71fb4cfaf0e
Create Date: 2026-04-13

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h1a2b3c4d5e6"
down_revision: str | None = "a71fb4cfaf0e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("drive_files", sa.Column("rag_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("drive_files", "rag_error")
