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
