"""remove_timestamps_from_drive_file_chunk_links

Revision ID: e1f2a3b4c5d6
Revises: c8f2d4a67e19
Create Date: 2026-04-07 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "c8f2d4a67e19"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop timestamp columns from the immutable pivot table."""
    op.drop_column("rag_drive_file_chunk_links", "created_at")
    op.drop_column("rag_drive_file_chunk_links", "updated_at")


def downgrade() -> None:
    """Re-add timestamp columns."""
    op.add_column(
        "rag_drive_file_chunk_links",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')"),
        ),
    )
    op.add_column(
        "rag_drive_file_chunk_links",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')"),
        ),
    )
