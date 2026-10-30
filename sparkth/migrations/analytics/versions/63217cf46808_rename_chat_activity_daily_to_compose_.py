"""rename chat_activity_daily to compose_activity_daily

Revision ID: 63217cf46808
Revises: 627d68f0c2c4
Create Date: 2026-10-29 15:40:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "63217cf46808"
down_revision: Union[str, Sequence[str], None] = "627d68f0c2c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_activity_daily(prefix: str) -> None:
    """Create ``<prefix>_activity_daily`` over the ``<prefix>.*`` events, with its refresh policy.

    The definition and policy are 627d68f0c2c4's, with ``prefix`` as the plugin name.
    """
    # WITH NO DATA keeps the backfill out of Alembic's transaction.
    op.execute(
        f"""
        CREATE MATERIALIZED VIEW {prefix}_activity_daily
        WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
        SELECT time_bucket('1 day', occurred_at) AS day,
               event_type,
               CASE event_type WHEN '{prefix}.tool_invoked'          THEN payload->>'tool_name'
                               WHEN '{prefix}.turn_failed'           THEN payload->>'cause'
                               WHEN '{prefix}.rag_search_completed'  THEN payload->>'result' END AS dimension,
               payload->>'outcome' AS outcome,
               count(*) AS event_count
        FROM raw_events
        WHERE event_type IN ('{prefix}.conversation_started', '{prefix}.message_sent', '{prefix}.tool_invoked',
                             '{prefix}.document_attached', '{prefix}.document_detached', '{prefix}.turn_failed',
                             '{prefix}.rag_search_completed')
        GROUP BY day, event_type, dimension, outcome
        WITH NO DATA
        """
    )
    op.execute(
        f"""
        SELECT add_continuous_aggregate_policy(
            '{prefix}_activity_daily',
            start_offset      => INTERVAL '3 days',
            end_offset        => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour'
        )
        """
    )


def upgrade() -> None:
    # The aggregate follows the plugin's rename to compose. A continuous aggregate's query can't
    # be altered, so it is dropped (which removes its refresh policy) and recreated; the `migrate`
    # command's backfill fills it. TimescaleDB-only; on SQLite the read path aggregates raw_events.
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_activity_daily")
    _create_activity_daily("compose")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP MATERIALIZED VIEW IF EXISTS compose_activity_daily")
    _create_activity_daily("chat")
