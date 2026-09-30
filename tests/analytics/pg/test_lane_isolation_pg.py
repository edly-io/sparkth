"""The TimescaleDB lane refreshes continuous aggregates itself, so nothing else may.

``add_continuous_aggregate_policy`` starts the policy's first run as soon as the migration
creates it. TimescaleDB allows one refresh per aggregate at a time, so a first run that
overlaps a test's own full refresh fails that test with ``LockNotAvailableError``.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.pg


async def test_no_refresh_policy_runs_behind_the_tests(pg_engine: AsyncEngine) -> None:
    async with pg_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT j.job_id, j.scheduled, s.job_status"
                    " FROM timescaledb_information.jobs j"
                    " LEFT JOIN timescaledb_information.job_stats s USING (job_id)"
                    " WHERE j.proc_name = 'policy_refresh_continuous_aggregate'"
                )
            )
        ).all()

    assert rows, "the migrations create a refresh policy, so the lane must find one"
    assert [row for row in rows if row.scheduled or row.job_status == "Running"] == []
