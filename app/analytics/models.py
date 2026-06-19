"""Schema registry for the analytics database.

Analytics tables live in a **separate** database from the application's models,
so they must not be registered on ``SQLModel.metadata`` (which maps to the app
database and drives the app's Alembic autogenerate). All analytics tables and
their Alembic migrations target this dedicated :class:`~sqlalchemy.MetaData`
instead.

This module currently defines only the empty registry — the foundation phase
adds no tables. TimescaleDB hypertables and continuous aggregates are added in
later phases.
"""

from sqlalchemy import MetaData

# Registry every analytics table attaches to. The analytics Alembic env
# (app/migrations_analytics/env.py) uses this as its target_metadata.
analytics_metadata = MetaData()
