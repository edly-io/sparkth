"""add searches to chat_activity_daily

Revision ID: 627d68f0c2c4
Revises: 53bf2193ac04
Create Date: 2026-10-20 12:01:27.250238

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "627d68f0c2c4"
down_revision: Union[str, Sequence[str], None] = "53bf2193ac04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Adds chat.rag_search_completed (dimension = its result). A continuous aggregate's query
    # can't be altered, so it is dropped (which removes its refresh policy) and recreated;
    # raw_events has no retention policy, so the `migrate` command's backfill restores every
    # bucket. TimescaleDB-only; on SQLite the read path aggregates raw_events directly.
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_activity_daily")
    # WITH NO DATA keeps the backfill out of Alembic's transaction.
    op.execute(
        """
        CREATE MATERIALIZED VIEW chat_activity_daily
        WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
        SELECT time_bucket('1 day', occurred_at) AS day,
               event_type,
               CASE event_type WHEN 'chat.tool_invoked'          THEN payload->>'tool_name'
                               WHEN 'chat.turn_failed'           THEN payload->>'cause'
                               WHEN 'chat.rag_search_completed'  THEN payload->>'result' END AS dimension,
               payload->>'outcome' AS outcome,
               count(*) AS event_count
        FROM raw_events
        WHERE event_type IN ('chat.conversation_started', 'chat.message_sent', 'chat.tool_invoked',
                             'chat.document_attached', 'chat.document_detached', 'chat.turn_failed',
                             'chat.rag_search_completed')
        GROUP BY day, event_type, dimension, outcome
        WITH NO DATA
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy(
            'chat_activity_daily',
            start_offset      => INTERVAL '3 days',
            end_offset        => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour'
        )
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_activity_daily")
    # The definition and policy from 3b6c4d3ec24f, verbatim.
    op.execute(
        """
        CREATE MATERIALIZED VIEW chat_activity_daily
        WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
        SELECT time_bucket('1 day', occurred_at) AS day,
               event_type,
               CASE event_type WHEN 'chat.tool_invoked' THEN payload->>'tool_name'
                               WHEN 'chat.turn_failed'  THEN payload->>'cause' END AS dimension,
               payload->>'outcome' AS outcome,
               count(*) AS event_count
        FROM raw_events
        WHERE event_type IN ('chat.conversation_started', 'chat.message_sent', 'chat.tool_invoked',
                             'chat.document_attached', 'chat.document_detached', 'chat.turn_failed')
        GROUP BY day, event_type, dimension, outcome
        WITH NO DATA
        """
    )
    op.execute(
        """
        SELECT add_continuous_aggregate_policy(
            'chat_activity_daily',
            start_offset      => INTERVAL '3 days',
            end_offset        => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour'
        )
        """
    )
