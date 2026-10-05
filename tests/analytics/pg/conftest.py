"""Fixtures for the TimescaleDB test lane.

Most of the suite runs on in-memory SQLite. A small set of tests genuinely needs a
real PostgreSQL/TimescaleDB — the ones exercising continuous aggregates, whose SQL
(``_PG_SQL`` in :mod:`sparkth.core.analytics.reads`) and DDL (the analytics migrations)
SQLite cannot represent. Those tests carry the ``pg`` marker (applied module-wide via
``pytestmark = pytest.mark.pg``, not a per-function decorator) and live under this
directory; they run only when ``ANALYTICS_TEST_PG_URL`` points at a real instance and are
skipped otherwise (so a plain ``pytest`` on a dev machine, and the default CI job, stay
green with zero extra infrastructure).

Continuous aggregates cannot use the rest of the suite's transaction-free isolation:
``refresh_continuous_aggregate`` cannot run inside a transaction block, and materialization
is asynchronous. So isolation here is *commit + reset* — each test starts from a truncated
event store and emptied aggregates, not a rolled-back transaction.
"""

import os
import subprocess
import sys
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

_PG_URL_ENV = "ANALYTICS_TEST_PG_URL"
# tests/analytics/pg/conftest.py -> repo root is three parents up from the file's dir.
_REPO_ROOT = Path(__file__).resolve().parents[3]

_LIST_CAGGS = text("SELECT view_name FROM timescaledb_information.continuous_aggregates ORDER BY view_name")
_REFRESH_CAGG = text("CALL refresh_continuous_aggregate(CAST(:name AS regclass), NULL, NULL)")
_PAUSE_REFRESH_POLICIES = text(
    "SELECT alter_job(job_id, scheduled => false) FROM timescaledb_information.jobs"
    " WHERE proc_name = 'policy_refresh_continuous_aggregate'"
)
# A running policy shows in job_stats and as its own backend; either means it still holds the aggregate.
_REFRESH_POLICY_RUNNING = text(
    "SELECT EXISTS (SELECT 1 FROM timescaledb_information.job_stats s"
    " JOIN timescaledb_information.jobs j USING (job_id)"
    " WHERE j.proc_name = 'policy_refresh_continuous_aggregate' AND s.job_status = 'Running')"
    " OR EXISTS (SELECT 1 FROM pg_stat_activity"
    " WHERE application_name LIKE 'Refresh Continuous Aggregate Policy%')"
)
_POLICY_DRAIN_TIMEOUT_S = 60


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip every ``pg``-marked test in this directory when no Timescale URL is configured."""
    if os.environ.get(_PG_URL_ENV):
        return
    skip = pytest.mark.skip(reason=f"{_PG_URL_ENV} not set; TimescaleDB lane not exercised")
    for item in items:
        if "pg" in item.keywords:
            item.add_marker(skip)


async def _refresh_all_caggs(engine: AsyncEngine) -> None:
    # AUTOCOMMIT: refresh_continuous_aggregate cannot run inside a transaction block.
    async with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
        for row in (await conn.execute(_LIST_CAGGS)).all():
            await conn.execute(_REFRESH_CAGG, {"name": row.view_name})


@pytest.fixture(scope="session")
def pg_url() -> str:
    url = os.environ.get(_PG_URL_ENV)
    if not url:
        pytest.skip(f"{_PG_URL_ENV} not set; skipping TimescaleDB lane")
    return url


@pytest.fixture(scope="session")
def _pg_migrated(pg_url: str) -> None:
    """Apply the analytics migrations to the test database — the same DDL production runs.

    Running the real migrations (rather than ``metadata.create_all``) is what makes the
    continuous aggregate exist here, and it doubles as a check that the Timescale-specific
    migration DDL actually applies on PostgreSQL. A subprocess is used so Alembic reads a
    fresh ``ANALYTICS_DATABASE_URL`` (the in-process settings are cached to SQLite).
    """
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic_analytics.ini", "upgrade", "head"],
        cwd=_REPO_ROOT,
        env={**os.environ, "ANALYTICS_DATABASE_URL": pg_url},
        check=True,
    )
    _stop_refresh_policies(pg_url)


def _stop_refresh_policies(pg_url: str) -> None:
    """Pause every refresh policy and wait out a run already under way.

    The migration's ``add_continuous_aggregate_policy`` starts the policy's first run
    straight away, at a moment the background scheduler picks. TimescaleDB allows one
    refresh per aggregate at a time, so that run failed whichever test's own full refresh it
    overlapped (``LockNotAvailableError``). The tests refresh explicitly and never rely on
    the policy, so pausing it leaves them as the only refresher.
    """
    engine = create_engine(pg_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(_PAUSE_REFRESH_POLICIES)
            deadline = time.monotonic() + _POLICY_DRAIN_TIMEOUT_S
            while conn.execute(_REFRESH_POLICY_RUNNING).scalar():
                if time.monotonic() > deadline:
                    raise TimeoutError(f"a refresh policy was still running after {_POLICY_DRAIN_TIMEOUT_S}s")
                time.sleep(0.1)
    finally:
        engine.dispose()


@pytest.fixture
async def pg_engine(pg_url: str, _pg_migrated: None) -> AsyncGenerator[AsyncEngine]:
    engine = create_async_engine(pg_url.replace("postgresql://", "postgresql+asyncpg://"))
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def pg_analytics_session(pg_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """A session on the Timescale analytics DB, starting from a clean, emptied state.

    Resets before yielding (truncate the event store, then full-refresh every aggregate so
    its materialization is emptied) since caggs cannot be isolated by transaction rollback.
    """
    async with pg_engine.begin() as conn:
        await conn.execute(text("TRUNCATE raw_events"))
    await _refresh_all_caggs(pg_engine)
    async with AsyncSession(pg_engine) as session:
        yield session


@pytest.fixture
def pg_refresh(pg_engine: AsyncEngine) -> Callable[[], Awaitable[None]]:
    """Full-refresh all continuous aggregates — call after seeding, before reading."""

    async def _refresh() -> None:
        await _refresh_all_caggs(pg_engine)

    return _refresh
