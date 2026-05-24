from collections.abc import Generator
from typing import Any

import pytest
from sqlmodel import Session, select
from typer.testing import CliRunner

from app.cli import users as users_cli
from app.models.user import User


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def cli_engine(
    sync_engine: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[Any, None, None]:
    """Point the CLI's `get_engine` at the in-memory test engine."""
    monkeypatch.setattr(users_cli, "get_engine", lambda: sync_engine)
    yield sync_engine


def test_create_user_marks_email_unverified_by_default(runner: CliRunner, cli_engine: Any) -> None:
    result = runner.invoke(
        users_cli.app,
        [
            "create-user",
            "--username",
            "alice",
            "--email",
            "alice@example.com",
            "--password",
            "Pw-alice-1!",
        ],
    )
    assert result.exit_code == 0, result.output
    with Session(cli_engine) as session:
        user = session.exec(select(User).where(User.username == "alice")).one()
        assert user.email_verified is False
        assert user.email_verified_at is None


def test_create_user_can_seed_a_verified_superuser(runner: CliRunner, cli_engine: Any) -> None:
    result = runner.invoke(
        users_cli.app,
        [
            "create-user",
            "--username",
            "admin",
            "--email",
            "admin@sparkth.local",
            "--password",
            "Sparkth-admin-1!",
            "--superuser",
            "--email-verified",
        ],
    )
    assert result.exit_code == 0, result.output
    with Session(cli_engine) as session:
        user = session.exec(select(User).where(User.username == "admin")).one()
        assert user.is_superuser is True
        assert user.email_verified is True
        assert user.email_verified_at is not None
