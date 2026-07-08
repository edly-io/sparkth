"""create raw_events hypertable

Revision ID: 23ceb3cb8918
Revises: 5a6cb47bb31b
Create Date: 2026-06-22 13:26:10.604202

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "23ceb3cb8918"
down_revision: Union[str, Sequence[str], None] = "5a6cb47bb31b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "raw_events",
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
    )
    bind = op.get_bind()
    # TimescaleDB hypertable: Postgres-only. No-op on SQLite (tests).
    if bind.dialect.name == "postgresql":
        op.execute("SELECT create_hypertable('raw_events', 'occurred_at')")


def downgrade() -> None:
    op.drop_table("raw_events")
