"""Administrative maintenance operations over the analytics database.

Unlike the read path (:mod:`sparkth.core.analytics.reads`), which only issues
``SELECT``s, this module runs Timescale-specific administrative procedures — currently
the one-off backfill of continuous aggregates. Exposed to the CLI via
``sparkth.lib.analytics``.
"""

from sqlalchemy import text

from sparkth.core.analytics.db import get_analytics_engine
from sparkth.core.analytics.exceptions import ContinuousAggregateNotFound
from sparkth.lib.log import get_logger

logger = get_logger(__name__)

# Every continuous aggregate registered with TimescaleDB, so the backfill covers all of
# them (present and future) rather than a hard-coded list that drifts as rollups are added.
_LIST_CONTINUOUS_AGGREGATES = text(
    "SELECT view_name FROM timescaledb_information.continuous_aggregates ORDER BY view_name"
)

# ``refresh_continuous_aggregate`` is a TimescaleDB stored procedure (invoked with CALL,
# not SELECT) and cannot run inside a transaction block — so it is executed on an
# AUTOCOMMIT connection below. ``NULL, NULL`` refreshes the entire range, materializing
# all history rather than only the trailing window the aggregate's policy covers. The
# target is bound and cast to ``regclass`` so a caller-supplied name is never interpolated
# into SQL.
_REFRESH_AGGREGATE = text("CALL refresh_continuous_aggregate(CAST(:name AS regclass), NULL, NULL)")


async def backfill_continuous_aggregates(name: str | None = None) -> list[str] | None:
    """Materialize the full history of continuous aggregates (all, or one by ``name``).

    Continuous aggregates are created ``WITH NO DATA`` (so creation does not backfill
    inside Alembic's transaction), and their refresh policies only cover a trailing
    window (``start_offset``). Without a one-off full refresh, buckets older than that
    window fall below the materialization watermark once the first policy run advances it
    and disappear from the view — so any pre-migration history is silently lost. Run this
    once after applying an aggregate's migration on PostgreSQL/TimescaleDB; it is
    idempotent and safe to re-run.

    Args:
        name: Refresh only this aggregate. When ``None`` (default), refresh every
            continuous aggregate discovered in the TimescaleDB catalog.

    Returns:
        The list of aggregate names refreshed (possibly empty if none are registered), or
        ``None`` if skipped because the analytics database is not PostgreSQL/TimescaleDB
        (e.g. SQLite in tests/e2e, where continuous aggregates do not exist and the read
        path aggregates ``raw_events`` directly).

    Raises:
        ContinuousAggregateNotFound: if ``name`` is given but no such aggregate exists.
    """
    engine = get_analytics_engine()
    if engine.dialect.name != "postgresql":
        logger.info(
            "Skipping continuous-aggregate backfill: analytics dialect is '%s', not 'postgresql'",
            engine.dialect.name,
        )
        return None
    # AUTOCOMMIT because refresh_continuous_aggregate cannot run inside a transaction block.
    async with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
        available = [row.view_name for row in (await conn.execute(_LIST_CONTINUOUS_AGGREGATES)).all()]
        if name is not None:
            if name not in available:
                raise ContinuousAggregateNotFound(name)
            targets = [name]
        else:
            targets = available
        for target in targets:
            await conn.execute(_REFRESH_AGGREGATE, {"name": target})
    logger.info("Refreshed %d continuous aggregate(s): %s", len(targets), ", ".join(targets) or "(none)")
    return targets
