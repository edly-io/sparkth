import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_analytics_migrations_apply_on_sqlite(tmp_path: Path) -> None:
    db_file = tmp_path / "analytics_migr.db"
    env = {
        "ANALYTICS_DATABASE_URL": f"sqlite+aiosqlite:///{db_file}",
    }

    full_env = {**os.environ, **env}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic_analytics.ini", "upgrade", "head"],
        capture_output=True,
        text=True,
        env=full_env,
    )
    assert result.returncode == 0, result.stderr


def test_raw_events_table_created_on_sqlite(tmp_path: Path) -> None:
    db_file = tmp_path / "analytics_migr_tables.db"
    full_env = {**os.environ, "ANALYTICS_DATABASE_URL": f"sqlite+aiosqlite:///{db_file}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic_analytics.ini", "upgrade", "head"],
        capture_output=True,
        text=True,
        env=full_env,
    )
    assert result.returncode == 0, result.stderr

    conn = sqlite3.connect(db_file)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='raw_events'").fetchall()
    finally:
        conn.close()
    assert rows == [("raw_events",)]


def test_login_activity_cagg_migration_is_noop_on_sqlite(tmp_path: Path) -> None:
    """The continuous-aggregate migration must apply cleanly on SQLite as a no-op.

    Continuous aggregates are TimescaleDB-only; on SQLite the migration must skip
    its DDL so the whole analytics lineage still upgrades to head (the environment
    the test suite and e2e run against). The Postgres path is verified manually
    against a real TimescaleDB (see the plan's manual-verification step).
    """
    db_file = tmp_path / "analytics_cagg.db"
    full_env = {**os.environ, "ANALYTICS_DATABASE_URL": f"sqlite+aiosqlite:///{db_file}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic_analytics.ini", "upgrade", "head"],
        capture_output=True,
        text=True,
        env=full_env,
    )
    assert result.returncode == 0, result.stderr

    conn = sqlite3.connect(db_file)
    try:
        views = conn.execute("SELECT name FROM sqlite_master WHERE name = 'login_activity_daily'").fetchall()
    finally:
        conn.close()
    # No-op on SQLite: the continuous aggregate is not created here.
    assert views == []


def _alembic(db_file: Path, *args: str) -> None:
    full_env = {**os.environ, "ANALYTICS_DATABASE_URL": f"sqlite+aiosqlite:///{db_file}"}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic_analytics.ini", *args],
        capture_output=True,
        text=True,
        env=full_env,
    )
    assert result.returncode == 0, result.stderr


def test_v1_login_events_swap_username_for_password_method(tmp_path: Path) -> None:
    """user.logged_in v1 stored the user's username; upgrading replaces it with ``method: password``.

    Only password login emitted before, so every stored row gets that method. The row itself
    stays, so login history keeps counting, and other events are not touched.
    """
    db_file = tmp_path / "analytics_login_method.db"
    _alembic(db_file, "upgrade", "287f281e6558")

    conn = sqlite3.connect(db_file)
    try:
        conn.executemany(
            "INSERT INTO raw_events (occurred_at, received_at, event_type, event_version, actor_id, payload)"
            " VALUES ('2026-09-01 10:00:00', '2026-09-01 10:00:00', ?, ?, ?, ?)",
            [
                ("user.logged_in", 1, "7", '{"username": "alice"}'),
                (
                    "assessment.submitted",
                    1,
                    "7",
                    '{"learner_id": "u1", "competency_id": "c1", "score": 1, "passed": true}',
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    _alembic(db_file, "upgrade", "head")

    conn = sqlite3.connect(db_file)
    try:
        rows = conn.execute("SELECT event_type, actor_id, payload FROM raw_events ORDER BY event_type").fetchall()
    finally:
        conn.close()
    assert [(event_type, actor_id, json.loads(payload)) for event_type, actor_id, payload in rows] == [
        ("assessment.submitted", "7", {"learner_id": "u1", "competency_id": "c1", "score": 1, "passed": True}),
        ("user.logged_in", "7", {"method": "password"}),
    ]


def test_login_activity_by_method_cagg_migration_is_noop_on_sqlite(tmp_path: Path) -> None:
    """The by-method continuous aggregate is TimescaleDB-only; on SQLite upgrading skips it."""
    db_file = tmp_path / "analytics_cagg_by_method.db"
    _alembic(db_file, "upgrade", "head")

    conn = sqlite3.connect(db_file)
    try:
        views = conn.execute("SELECT name FROM sqlite_master WHERE name = 'login_activity_daily_by_method'").fetchall()
    finally:
        conn.close()
    assert views == []
