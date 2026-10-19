"""create googledrive_documents_daily cagg

Revision ID: 53bf2193ac04
Revises: 9add2895a73c
Create Date: 2026-10-19 13:07:48.824638

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "53bf2193ac04"
down_revision: Union[str, Sequence[str], None] = "9add2895a73c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Daily Drive document outcomes, read by the googledrive plugin's ``get_drive_documents``.
    # Raw SQL because continuous aggregates have no SQLAlchemy construct and are invisible to
    # autogenerate. TimescaleDB-only; on SQLite the read path aggregates raw_events directly.
    if op.get_bind().dialect.name != "postgresql":
        return
    # WITH NO DATA keeps the backfill out of Alembic's transaction; the `migrate` command
    # backfills every continuous aggregate afterwards (`make analytics-backfill` for one).
    op.execute(
        """
        CREATE MATERIALIZED VIEW googledrive_documents_daily
        WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
        SELECT time_bucket('1 day', occurred_at) AS day,
               payload->>'outcome' AS outcome,
               count(*) AS document_count,
               sum((payload->>'seconds_to_final')::bigint) AS seconds_total
        FROM raw_events
        WHERE event_type = 'google-drive.document_processed'
        GROUP BY day, outcome
        WITH NO DATA
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy(
            'googledrive_documents_daily',
            start_offset      => INTERVAL '3 days',
            end_offset        => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour'
        )
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP MATERIALIZED VIEW IF EXISTS googledrive_documents_daily")
