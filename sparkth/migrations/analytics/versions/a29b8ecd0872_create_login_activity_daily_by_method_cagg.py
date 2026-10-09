"""create login_activity_daily_by_method cagg

Revision ID: a29b8ecd0872
Revises: 6ccbebfb6a25
Create Date: 2026-10-08 12:17:21.501796

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a29b8ecd0872"
down_revision: Union[str, Sequence[str], None] = "6ccbebfb6a25"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Daily login counts split by sign-in method, read by ``get_logins``. Same shape and
    # refresh policy as ``login_activity_daily``, which stays in place for
    # ``get_login_activity``. Raw SQL because continuous aggregates have no
    # SQLAlchemy construct and are invisible to autogenerate.
    bind = op.get_bind()
    # TimescaleDB-only; on SQLite the read path aggregates raw_events directly.
    if bind.dialect.name != "postgresql":
        return
    # WITH NO DATA keeps the backfill out of Alembic's transaction; the `migrate` command
    # backfills every continuous aggregate afterwards (`make analytics-backfill` for one).
    op.execute(
        """
        CREATE MATERIALIZED VIEW login_activity_daily_by_method
        WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
        SELECT time_bucket('1 day', occurred_at) AS day,
               payload->>'method'                AS method,
               count(*)                          AS login_count
        FROM raw_events
        WHERE event_type = 'user.logged_in'
        GROUP BY day, method
        WITH NO DATA
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy(
            'login_activity_daily_by_method',
            start_offset      => INTERVAL '3 days',
            end_offset        => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour'
        )
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP MATERIALIZED VIEW IF EXISTS login_activity_daily_by_method")
