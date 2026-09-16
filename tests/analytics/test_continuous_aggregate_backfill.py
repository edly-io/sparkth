"""Tests for the continuous-aggregate backfill.

The real refresh (``CALL refresh_continuous_aggregate``) only runs on
PostgreSQL/TimescaleDB, which the SQLite test suite cannot exercise. So we test the
parts that *are* reachable here: the non-Postgres no-op guard against the real engine,
and — via a stub engine — that the Postgres branch discovers aggregates from the catalog
and issues a full-range refresh for each on an AUTOCOMMIT connection.
"""

import asyncio
import types
from collections.abc import Iterator
from typing import cast

import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine
from typer.testing import CliRunner

import sparkth.core.analytics.maintenance as maintenance
from sparkth.cli.main import app as root_cli
from sparkth.lib.analytics import ContinuousAggregateNotFound, backfill_continuous_aggregates

_LIST_PREFIX = "SELECT view_name"


class _FakeResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _PgError(Exception):
    """A driver error carrying the SQLSTATE the way asyncpg's SQLAlchemy adapter does."""

    def __init__(self, pgcode: str, message: str) -> None:
        super().__init__(message)
        self.pgcode = pgcode


def _lock_not_available() -> DBAPIError:
    """The error TimescaleDB raises when another refresh of the same aggregate is running."""
    orig = _PgError(
        "55P03", 'could not refresh continuous aggregate "login_activity_daily" due to a concurrent refresh'
    )
    return DBAPIError("CALL refresh_continuous_aggregate(...)", {}, orig)


class _FakeConn:
    def __init__(
        self,
        caggs: list[str],
        executed: list[tuple[str, object]],
        failures: Iterator[Exception] | None = None,
    ) -> None:
        self._caggs = caggs
        self._executed = executed
        # Exceptions to raise from successive refresh CALLs, then succeed once exhausted.
        self._failures = failures if failures is not None else iter(())

    async def __aenter__(self) -> "_FakeConn":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def execute(self, statement: object, params: object = None) -> _FakeResult | None:
        sql = str(statement)
        self._executed.append((sql, params))
        if sql.startswith(_LIST_PREFIX):
            return _FakeResult([types.SimpleNamespace(view_name=name) for name in self._caggs])
        failure = next(self._failures, None)
        if failure is not None:
            raise failure
        return None


class _FakeEngine:
    """Stands in for the Postgres analytics engine so the PG branch is reachable on SQLite."""

    def __init__(self, caggs: list[str], failures: list[Exception] | None = None) -> None:
        self.dialect = types.SimpleNamespace(name="postgresql")
        self.caggs = caggs
        self.executed: list[tuple[str, object]] = []
        self.recorded_options: dict[str, object] = {}
        self._failures = iter(failures or [])

    def execution_options(self, **options: object) -> "_FakeEngine":
        self.recorded_options.update(options)
        return self

    def connect(self) -> _FakeConn:
        return _FakeConn(self.caggs, self.executed, self._failures)


def _refresh_calls(engine: _FakeEngine) -> list[object]:
    return [params for sql, params in engine.executed if sql.startswith("CALL refresh_continuous_aggregate")]


async def test_backfill_skips_on_non_postgres(analytics_session: object) -> None:
    # The test analytics DB is SQLite, where continuous aggregates do not exist; the
    # backfill must no-op (returning None) rather than issue Timescale-only SQL.
    result = await backfill_continuous_aggregates()

    assert result is None


async def test_backfill_refreshes_all_discovered(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _FakeEngine(["assessment_daily", "login_activity_daily"])
    monkeypatch.setattr(maintenance, "get_analytics_engine", lambda: engine)

    result = await backfill_continuous_aggregates()

    assert result == ["assessment_daily", "login_activity_daily"]
    assert engine.recorded_options == {"isolation_level": "AUTOCOMMIT"}
    assert _refresh_calls(engine) == [{"name": "assessment_daily"}, {"name": "login_activity_daily"}]


async def test_backfill_named_aggregate_refreshes_only_that_one(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _FakeEngine(["assessment_daily", "login_activity_daily"])
    monkeypatch.setattr(maintenance, "get_analytics_engine", lambda: engine)

    result = await backfill_continuous_aggregates("login_activity_daily")

    assert result == ["login_activity_daily"]
    assert _refresh_calls(engine) == [{"name": "login_activity_daily"}]


@pytest.fixture
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Record the backoff sleeps instead of waiting them out."""
    slept: list[float] = []

    async def _sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", _sleep)
    return slept


async def test_backfill_retries_when_a_concurrent_refresh_holds_the_lock(
    monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]
) -> None:
    """The aggregate's own policy job runs the moment the migration creates it, so a
    backfill (or the test lane's reset) that follows straight after can find the lock
    taken. That is a transient condition, not a failure: wait and try again."""
    engine = _FakeEngine(["login_activity_daily"], failures=[_lock_not_available(), _lock_not_available()])
    monkeypatch.setattr(maintenance, "get_analytics_engine", lambda: engine)

    result = await backfill_continuous_aggregates()

    assert result == ["login_activity_daily"]
    assert _refresh_calls(engine) == [{"name": "login_activity_daily"}] * 3
    assert len(no_sleep) == 2


async def test_backfill_gives_up_after_the_retry_budget(monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]) -> None:
    engine = _FakeEngine(["login_activity_daily"], failures=[_lock_not_available()] * 50)
    monkeypatch.setattr(maintenance, "get_analytics_engine", lambda: engine)

    with pytest.raises(DBAPIError):
        await backfill_continuous_aggregates()

    assert len(_refresh_calls(engine)) == maintenance.REFRESH_LOCK_ATTEMPTS


async def test_backfill_does_not_retry_other_database_errors(
    monkeypatch: pytest.MonkeyPatch, no_sleep: list[float]
) -> None:
    orig = _PgError("42P01", "relation does not exist")
    engine = _FakeEngine(["login_activity_daily"], failures=[DBAPIError("CALL ...", {}, orig)])
    monkeypatch.setattr(maintenance, "get_analytics_engine", lambda: engine)

    with pytest.raises(DBAPIError):
        await backfill_continuous_aggregates()

    assert len(_refresh_calls(engine)) == 1
    assert no_sleep == []


async def test_backfill_accepts_an_explicit_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """The TimescaleDB test lane refreshes its own scratch database through this function."""
    engine = _FakeEngine(["login_activity_daily"])
    monkeypatch.setattr(maintenance, "get_analytics_engine", lambda: pytest.fail("must use the given engine"))

    result = await backfill_continuous_aggregates(engine=cast(AsyncEngine, engine))

    assert result == ["login_activity_daily"]


async def test_backfill_unknown_name_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _FakeEngine(["login_activity_daily"])
    monkeypatch.setattr(maintenance, "get_analytics_engine", lambda: engine)

    with pytest.raises(ContinuousAggregateNotFound):
        await backfill_continuous_aggregates("does_not_exist")

    assert _refresh_calls(engine) == []


def test_cli_reports_refreshed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _refreshed(name: str | None = None) -> list[str]:
        return ["login_activity_daily"]

    monkeypatch.setattr("sparkth.cli.analytics.backfill_continuous_aggregates", _refreshed)

    result = CliRunner().invoke(root_cli, ["analytics", "backfill-aggregates"])

    assert result.exit_code == 0
    assert "Refreshed 1 aggregate(s): login_activity_daily" in result.stdout


def test_cli_reports_skipped_on_non_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _skipped(name: str | None = None) -> None:
        return None

    monkeypatch.setattr("sparkth.cli.analytics.backfill_continuous_aggregates", _skipped)

    result = CliRunner().invoke(root_cli, ["analytics", "backfill-aggregates"])

    assert result.exit_code == 0
    assert "Skipped" in result.stdout


def test_cli_reports_unknown_name(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _missing(name: str | None = None) -> list[str]:
        raise ContinuousAggregateNotFound(name or "")

    monkeypatch.setattr("sparkth.cli.analytics.backfill_continuous_aggregates", _missing)

    result = CliRunner().invoke(root_cli, ["analytics", "backfill-aggregates", "--name", "nope"])

    assert result.exit_code == 1
    assert "nope" in result.stdout
