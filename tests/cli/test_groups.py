"""Tests for the group CLI commands (sparkth/cli/groups.py).
Authored with LLM (Claude) assistance."""

import pytest
import typer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from typer.testing import CliRunner

from sparkth.cli.main import app as root_cli
from sparkth.core.models.user import User
from sparkth.core.permissions import groups as group_engine
from sparkth.core.permissions.models import GroupMembership, GroupRoleAssignment, Role


async def _seed_user_and_group(session: AsyncSession) -> tuple[User, int]:
    user = User(name="T", username="alice", email="alice@example.com", hashed_password="x")
    session.add(user)
    await session.flush()
    group = await group_engine.create_group("cs-staff", None, session)
    assert user.id is not None and group.id is not None
    await session.commit()
    return user, group.id


async def test_add_member_happy_path(session: AsyncSession, capsys: pytest.CaptureFixture[str]) -> None:
    from sparkth.cli.groups import _add_member

    user, group_id = await _seed_user_and_group(session)
    await _add_member("alice", "cs-staff")
    memberships = (await session.exec(select(GroupMembership).where(GroupMembership.group_id == group_id))).all()
    assert len(memberships) == 1
    assert memberships[0].user_id == user.id
    assert "cs-staff" in capsys.readouterr().out


async def test_add_member_unknown_user_exits(session: AsyncSession) -> None:
    from sparkth.cli.groups import _add_member

    await _seed_user_and_group(session)
    with pytest.raises(typer.Exit) as excinfo:
        await _add_member("nobody", "cs-staff")
    assert excinfo.value.exit_code == 1


async def test_add_member_unknown_group_exits(session: AsyncSession) -> None:
    from sparkth.cli.groups import _add_member

    await _seed_user_and_group(session)
    with pytest.raises(typer.Exit) as excinfo:
        await _add_member("alice", "nope")
    assert excinfo.value.exit_code == 1


async def test_remove_member_happy_path(session: AsyncSession, capsys: pytest.CaptureFixture[str]) -> None:
    from sparkth.cli.groups import _add_member, _remove_member

    user, group_id = await _seed_user_and_group(session)
    await _add_member("alice", "cs-staff")
    await _remove_member("alice", "cs-staff")
    memberships = (await session.exec(select(GroupMembership).where(GroupMembership.group_id == group_id))).all()
    assert len(memberships) == 1
    assert memberships[0].is_deleted is True
    assert "cs-staff" in capsys.readouterr().out


async def test_remove_member_unknown_user_exits(session: AsyncSession) -> None:
    from sparkth.cli.groups import _remove_member

    await _seed_user_and_group(session)
    with pytest.raises(typer.Exit) as excinfo:
        await _remove_member("nobody", "cs-staff")
    assert excinfo.value.exit_code == 1


async def test_remove_member_unknown_group_exits(session: AsyncSession) -> None:
    from sparkth.cli.groups import _remove_member

    await _seed_user_and_group(session)
    with pytest.raises(typer.Exit) as excinfo:
        await _remove_member("alice", "nope")
    assert excinfo.value.exit_code == 1


async def test_assign_role_to_group_happy_path(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import sparkth.cli.groups as cli_groups

    monkeypatch.setattr(cli_groups, "get_plugin_loader", lambda: None)
    _, group_id = await _seed_user_and_group(session)
    session.add(Role(name="grader"))
    await session.commit()

    await cli_groups._assign_role_to_group("cs-staff", "grader", "global", None)

    assignments = (
        await session.exec(select(GroupRoleAssignment).where(GroupRoleAssignment.group_id == group_id))
    ).all()
    assert len(assignments) == 1
    assert assignments[0].scope == "global"
    assert "grader" in capsys.readouterr().out


async def test_assign_role_to_group_unknown_scope_exits(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    import sparkth.cli.groups as cli_groups

    monkeypatch.setattr(cli_groups, "get_plugin_loader", lambda: None)
    await _seed_user_and_group(session)
    with pytest.raises(typer.Exit) as excinfo:
        await cli_groups._assign_role_to_group("cs-staff", "grader", "bogus", None)
    assert excinfo.value.exit_code == 1


async def test_assign_role_to_group_unknown_group_exits(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    import sparkth.cli.groups as cli_groups

    monkeypatch.setattr(cli_groups, "get_plugin_loader", lambda: None)
    await _seed_user_and_group(session)
    with pytest.raises(typer.Exit) as excinfo:
        await cli_groups._assign_role_to_group("nope", "grader", "global", None)
    assert excinfo.value.exit_code == 1


async def test_assign_role_to_group_unknown_role_exits(session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> None:
    import sparkth.cli.groups as cli_groups

    monkeypatch.setattr(cli_groups, "get_plugin_loader", lambda: None)
    await _seed_user_and_group(session)
    with pytest.raises(typer.Exit) as excinfo:
        await cli_groups._assign_role_to_group("cs-staff", "nope", "global", None)
    assert excinfo.value.exit_code == 1


async def test_revoke_role_from_group_happy_path(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import sparkth.cli.groups as cli_groups

    monkeypatch.setattr(cli_groups, "get_plugin_loader", lambda: None)
    _, group_id = await _seed_user_and_group(session)
    session.add(Role(name="grader"))
    await session.commit()
    await cli_groups._assign_role_to_group("cs-staff", "grader", "global", None)

    await cli_groups._revoke_role_from_group("cs-staff", "grader", "global", None)

    assignments = (
        await session.exec(select(GroupRoleAssignment).where(GroupRoleAssignment.group_id == group_id))
    ).all()
    assert len(assignments) == 1
    assert assignments[0].is_deleted is True
    assert "grader" in capsys.readouterr().out


async def test_revoke_role_from_group_unknown_scope_exits(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sparkth.cli.groups as cli_groups

    monkeypatch.setattr(cli_groups, "get_plugin_loader", lambda: None)
    await _seed_user_and_group(session)
    with pytest.raises(typer.Exit) as excinfo:
        await cli_groups._revoke_role_from_group("cs-staff", "grader", "bogus", None)
    assert excinfo.value.exit_code == 1


async def test_revoke_role_from_group_unknown_group_exits(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sparkth.cli.groups as cli_groups

    monkeypatch.setattr(cli_groups, "get_plugin_loader", lambda: None)
    await _seed_user_and_group(session)
    with pytest.raises(typer.Exit) as excinfo:
        await cli_groups._revoke_role_from_group("nope", "grader", "global", None)
    assert excinfo.value.exit_code == 1


async def _fake_member_command(identifier: str, group_name: str) -> None:
    return None


async def _fake_group_role_command(group_name: str, role: str, scope: str, scope_object_id: str | None) -> None:
    return None


def test_cli_wires_remove_member(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.cli.groups._remove_member", _fake_member_command)
    result = CliRunner().invoke(root_cli, ["groups", "remove-member", "alice", "cs-staff"])
    assert result.exit_code == 0


def test_cli_wires_revoke_role_from_group(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sparkth.cli.groups._revoke_role_from_group", _fake_group_role_command)
    result = CliRunner().invoke(root_cli, ["groups", "revoke-role-from-group", "cs-staff", "grader"])
    assert result.exit_code == 0


def test_cli_wires_add_member(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake(identifier: str, group_name: str) -> None:
        return None

    monkeypatch.setattr("sparkth.cli.groups._add_member", _fake)
    result = CliRunner().invoke(root_cli, ["groups", "add-member", "alice", "cs-staff"])
    assert result.exit_code == 0


def test_cli_wires_assign_role_to_group(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake(group_name: str, role: str, scope: str, scope_object_id: str | None) -> None:
        return None

    monkeypatch.setattr("sparkth.cli.groups._assign_role_to_group", _fake)
    result = CliRunner().invoke(root_cli, ["groups", "assign-role-to-group", "cs-staff", "grader"])
    assert result.exit_code == 0
