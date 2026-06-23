import os
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
