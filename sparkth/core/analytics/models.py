"""Schema registry for the analytics database.

Analytics tables live in a **separate** database from the application's models,
so they must not be registered on ``SQLModel.metadata`` (which maps to the app
database and drives the app's Alembic autogenerate). All analytics tables and
their Alembic migrations target this dedicated :class:`~sqlalchemy.MetaData`
instead.

This module defines the registry and the first analytics table, ``raw_events``
(the append-only event store). TimescaleDB hypertable creation and continuous
aggregates are handled by the analytics migrations / later phases.
"""

import sqlalchemy as sa
from sqlalchemy import MetaData
from sqlalchemy.dialects.postgresql import JSONB

# Registry every analytics table attaches to. The analytics Alembic env
# (sparkth/migrations/analytics/env.py) uses this as its target_metadata.
analytics_metadata = MetaData()

# Append-only, time-partitioned store of validated analytics events. The analytics
# migration turns this into a TimescaleDB hypertable (partitioned on occurred_at)
# on PostgreSQL; on SQLite (tests) it stays a plain table. Event-specific fields
# live in ``payload`` — never as top-level columns — so the table stays generic.
raw_events = sa.Table(
    "raw_events",
    analytics_metadata,
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column("event_type", sa.Text(), nullable=False),
    sa.Column("event_version", sa.Integer(), nullable=False),
    sa.Column("actor_id", sa.Text(), nullable=True),
    sa.Column("payload", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
)
