"""drop login_activity_daily cagg

Login reads use ``login_activity_daily_by_method``.

Revision ID: ebad497c31e2
Revises: a29b8ecd0872
Create Date: 2026-10-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ebad497c31e2"
down_revision: Union[str, Sequence[str], None] = "a29b8ecd0872"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Raw SQL: continuous aggregates are TimescaleDB-only and invisible to autogenerate.
    # Dropping the aggregate also removes its refresh policy.
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP MATERIALIZED VIEW IF EXISTS login_activity_daily")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    # WITH NO DATA so creation does not backfill inside Alembic's transaction; run
    # `make analytics-backfill` afterwards to restore history.
    op.execute(
        """
        CREATE MATERIALIZED VIEW login_activity_daily
        WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
        SELECT time_bucket('1 day', occurred_at) AS day,
               count(*)                          AS login_count
        FROM raw_events
        WHERE event_type = 'user.logged_in'
        GROUP BY day
        WITH NO DATA
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy(
            'login_activity_daily',
            start_offset      => INTERVAL '3 days',
            end_offset        => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour'
        )
        """
    )
