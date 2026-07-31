"""Tests for the org CLI commands (sparkth/cli/org.py).
Authored with LLM (Claude) assistance."""

import pytest
import typer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from typer.testing import CliRunner

from sparkth.cli.main import app as root_cli
from sparkth.core.models.user import User
from sparkth.core.organization import units as unit_engine
from sparkth.core.organization.models import OrganizationMembership


async def _seed_user_and_unit(session: AsyncSession) -> tuple[User, int]:
    user = User(name="T", username="alice", email="alice@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    unit = await unit_engine.create_organizational_unit("CS Dept", None, None, session)
    assert user.id is not None and unit.id is not None
    await session.commit()
    return user, unit.id


async def test_add_member_happy_path(session: AsyncSession, capsys: pytest.CaptureFixture[str]) -> None:
    from sparkth.cli.organization import _add_member

    user, unit_id = await _seed_user_and_unit(session)
    await _add_member("alice", unit_id)
    rows = (
        await session.exec(
            select(OrganizationMembership).where(OrganizationMembership.organizational_unit_id == unit_id)
        )
    ).all()
    assert len(rows) == 1 and rows[0].user_id == user.id
    assert "CS Dept" in capsys.readouterr().out


async def test_add_member_unknown_user_exits(session: AsyncSession) -> None:
    from sparkth.cli.organization import _add_member

    _, unit_id = await _seed_user_and_unit(session)
    with pytest.raises(typer.Exit) as excinfo:
        await _add_member("nobody", unit_id)
    assert excinfo.value.exit_code == 1


async def test_add_member_unknown_unit_exits(session: AsyncSession) -> None:
    from sparkth.cli.organization import _add_member

    await _seed_user_and_unit(session)
    with pytest.raises(typer.Exit) as excinfo:
        await _add_member("alice", 999)
    assert excinfo.value.exit_code == 1


async def test_remove_member_happy_path(session: AsyncSession, capsys: pytest.CaptureFixture[str]) -> None:
    from sparkth.cli.organization import _add_member, _remove_member

    _, unit_id = await _seed_user_and_unit(session)
    await _add_member("alice", unit_id)
    await _remove_member("alice", unit_id)
    rows = (
        await session.exec(
            select(OrganizationMembership).where(OrganizationMembership.organizational_unit_id == unit_id)
        )
    ).all()
    assert len(rows) == 1 and rows[0].is_deleted is True
    assert "Removed" in capsys.readouterr().out


async def test_remove_member_unknown_unit_exits(session: AsyncSession) -> None:
    from sparkth.cli.organization import _remove_member

    await _seed_user_and_unit(session)
    with pytest.raises(typer.Exit) as excinfo:
        await _remove_member("alice", 999)
    assert excinfo.value.exit_code == 1


def test_cli_wires_add_member(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake(identifier: str, organizational_unit_id: int) -> None:
        return None

    monkeypatch.setattr("sparkth.cli.organization._add_member", _fake)
    result = CliRunner().invoke(root_cli, ["organization", "add-member", "alice", "1"])
    assert result.exit_code == 0


def test_cli_wires_remove_member(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake(identifier: str, organizational_unit_id: int) -> None:
        return None

    monkeypatch.setattr("sparkth.cli.organization._remove_member", _fake)
    result = CliRunner().invoke(root_cli, ["organization", "remove-member", "alice", "1"])
    assert result.exit_code == 0
