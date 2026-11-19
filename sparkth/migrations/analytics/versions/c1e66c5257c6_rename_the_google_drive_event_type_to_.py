"""rename the google drive event type to googledrive

Revision ID: c1e66c5257c6
Revises: 03f30f2e11aa
Create Date: 2026-11-17 15:22:44.294448

A plugin's event types are namespaced under its name, so renaming the plugin renames ``google-drive.*``
events. Stored events are rewritten, and the ``googledrive_documents_daily`` aggregate is recreated for the
new type. The downgrade restores the old type and aggregate.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1e66c5257c6"
down_revision: Union[str, Sequence[str], None] = "03f30f2e11aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Literal strings: a migration is a historical snapshot and must not import plugin constants.
_HYPHENATED = "google-drive.document_processed"
_PLAIN = "googledrive.document_processed"


def _rename_event_type(old: str, new: str) -> None:
    op.get_bind().execute(
        sa.text("UPDATE raw_events SET event_type = :new WHERE event_type = :old"), {"new": new, "old": old}
    )
    # A continuous aggregate's query can't be altered, so it is dropped (which removes its refresh
    # policy) and recreated; raw_events has no retention policy, so the `migrate` command's backfill
    # restores every bucket. TimescaleDB-only; on SQLite the read path aggregates raw_events directly.
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP MATERIALIZED VIEW IF EXISTS googledrive_documents_daily")
    # WITH NO DATA keeps the backfill out of Alembic's transaction.
    op.execute(
        f"""
        CREATE MATERIALIZED VIEW googledrive_documents_daily
        WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
        SELECT time_bucket('1 day', occurred_at) AS day,
               payload->>'outcome' AS outcome,
               count(*) AS document_count,
               sum((payload->>'seconds_to_final')::bigint) AS seconds_total
        FROM raw_events
        WHERE event_type = '{new}'
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


def upgrade() -> None:
    _rename_event_type(_HYPHENATED, _PLAIN)


def downgrade() -> None:
    _rename_event_type(_PLAIN, _HYPHENATED)
