"""create login_activity_daily cagg

Revision ID: 287f281e6558
Revises: 23ceb3cb8918
Create Date: 2026-07-08 11:52:47.971993

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "287f281e6558"
down_revision: Union[str, Sequence[str], None] = "23ceb3cb8918"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Raw SQL (op.execute) rather than SQLAlchemy Core DDL: continuous aggregates are a
    # TimescaleDB extension feature (CREATE MATERIALIZED VIEW ... WITH (timescaledb.continuous),
    # time_bucket(), add_continuous_aggregate_policy()) with no SQLAlchemy Core/ORM construct,
    # and are invisible to Alembic autogenerate. This mirrors the hypertable migration
    # (23ceb3cb8918), which likewise drops to raw SQL for the Timescale-specific step
    # (SELECT create_hypertable(...)). This revision was generated without --autogenerate.
    bind = op.get_bind()
    # Continuous aggregates are a TimescaleDB (Postgres) feature. On SQLite (tests,
    # e2e) this is a no-op — the S2 read path aggregates raw_events directly there.
    if bind.dialect.name != "postgresql":
        return
    # WITH NO DATA so creation does not backfill inside Alembic's transaction; the
    # continuous-aggregate policy below keeps it fresh going forward. The policy only
    # refreshes a trailing window, so run a one-off full backfill after this migration
    # to preserve pre-migration history: `make analytics-backfill` (refresh_continuous_aggregate
    # over the whole range) — otherwise buckets older than start_offset fall below the
    # materialization watermark once the first policy run advances it and vanish from the view.
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


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP MATERIALIZED VIEW IF EXISTS login_activity_daily")
