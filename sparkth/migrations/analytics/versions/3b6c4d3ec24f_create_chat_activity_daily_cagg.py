"""create chat_activity_daily cagg

Revision ID: 3b6c4d3ec24f
Revises: ebad497c31e2
Create Date: 2026-10-13 12:24:23.072210

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3b6c4d3ec24f"
down_revision: Union[str, Sequence[str], None] = "ebad497c31e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Daily chat authoring activity per event type, read by the chat plugin's
    # ``get_chat_activity``. ``dimension`` is the tool name or failure cause; ``outcome`` is
    # the tool call's outcome (NULL for tool rows recorded without one). Raw SQL because
    # continuous aggregates have no SQLAlchemy construct and are invisible to autogenerate.
    # TimescaleDB-only; on SQLite the read path aggregates raw_events directly.
    if op.get_bind().dialect.name != "postgresql":
        return
    # WITH NO DATA keeps the backfill out of Alembic's transaction; the `migrate` command
    # backfills every continuous aggregate afterwards (`make analytics-backfill` for one).
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


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP MATERIALIZED VIEW IF EXISTS chat_activity_daily")
