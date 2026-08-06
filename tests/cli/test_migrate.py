"""Tests for the one-shot `migrate` CLI command (sparkth.cli.migrate).

The command orchestrates Alembic and the continuous-aggregate backfill; the test
asserts the orchestration (both lineages upgraded, then the backfill) rather than
running real migrations, which need dialect-specific DDL.
"""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from sparkth.cli import migrate


def test_migrate_upgrades_both_lineages_then_backfills(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_upgrade(config: Config, revision: str) -> None:
        assert config.config_file_name is not None
        calls.append(("upgrade", Path(config.config_file_name).name, revision))

    async def fake_backfill(name: str | None = None) -> list[str]:
        calls.append(("backfill", str(name)))
        return ["course_activity_daily"]

    monkeypatch.setattr(command, "upgrade", fake_upgrade)
    monkeypatch.setattr(migrate, "backfill_continuous_aggregates", fake_backfill)

    migrate.migrate_command()

    assert calls == [
        ("upgrade", "alembic.ini", "head"),
        ("upgrade", "alembic_analytics.ini", "head"),
        ("backfill", "None"),
    ]


def test_migrate_reports_skipped_backfill_on_non_postgres(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(command, "upgrade", lambda config, revision: None)

    async def fake_backfill(name: str | None = None) -> None:
        return None

    monkeypatch.setattr(migrate, "backfill_continuous_aggregates", fake_backfill)

    migrate.migrate_command()

    assert "Skipped" in capsys.readouterr().out
