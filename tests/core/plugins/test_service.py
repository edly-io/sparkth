"""Behavioural tests for the plugin switches the service reads: which plugins are off for a user."""

from datetime import datetime, timezone
from typing import cast
from unittest.mock import patch

import pytest
from fastapi import Request
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin, UserPlugin
from sparkth.core.models.user import User
from sparkth.core.plugins.config_base import PluginConfig
from sparkth.core.plugins.service import (
    ConfigValidationError,
    PluginService,
    disabled_plugin_names,
    get_disabled_plugins,
)


async def _seed_plugin(session: AsyncSession, name: str, enabled: bool, deleted: bool = False) -> Plugin:
    plugin = Plugin(name=name, enabled=enabled, deleted_at=datetime.now(timezone.utc) if deleted else None)
    session.add(plugin)
    await session.commit()
    await session.refresh(plugin)
    return plugin


async def _seed_preference(
    session: AsyncSession, user_id: int, plugin: Plugin, enabled: bool, deleted: bool = False
) -> None:
    session.add(
        UserPlugin(
            user_id=user_id,
            plugin_id=cast(int, plugin.id),
            enabled=enabled,
            deleted_at=datetime.now(timezone.utc) if deleted else None,
        )
    )
    await session.commit()


async def _seed_other_user(session: AsyncSession) -> int:
    user = User(id=2, name="Other", username="other-user", email="other-user@example.com", hashed_password="x")
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return cast(int, user.id)


async def test_a_plugin_switched_off_system_wide_is_disabled(session: AsyncSession, current_user: User) -> None:
    await _seed_plugin(session, "stub", False)

    assert await disabled_plugin_names(cast(int, current_user.id), session) == {"stub"}


async def test_a_plugin_the_user_switched_off_is_disabled(session: AsyncSession, current_user: User) -> None:
    user_id = cast(int, current_user.id)
    plugin = await _seed_plugin(session, "stub", True)
    await _seed_preference(session, user_id, plugin, False)

    assert await disabled_plugin_names(user_id, session) == {"stub"}


async def test_a_plugin_with_no_preference_is_not_disabled(session: AsyncSession, current_user: User) -> None:
    await _seed_plugin(session, "stub", True)

    assert await disabled_plugin_names(cast(int, current_user.id), session) == set()


async def test_a_plugin_the_user_switched_on_is_not_disabled(session: AsyncSession, current_user: User) -> None:
    user_id = cast(int, current_user.id)
    plugin = await _seed_plugin(session, "stub", True)
    await _seed_preference(session, user_id, plugin, True)

    assert await disabled_plugin_names(user_id, session) == set()


async def test_a_plugin_with_no_registry_row_is_not_disabled(session: AsyncSession, current_user: User) -> None:
    assert "never-registered" not in await disabled_plugin_names(cast(int, current_user.id), session)


async def test_another_users_preference_does_not_disable_it(session: AsyncSession, current_user: User) -> None:
    plugin = await _seed_plugin(session, "stub", True)
    await _seed_preference(session, await _seed_other_user(session), plugin, False)

    assert await disabled_plugin_names(cast(int, current_user.id), session) == set()


async def test_a_deleted_preference_is_ignored(session: AsyncSession, current_user: User) -> None:
    user_id = cast(int, current_user.id)
    plugin = await _seed_plugin(session, "stub", True)
    await _seed_preference(session, user_id, plugin, False, True)

    assert await disabled_plugin_names(user_id, session) == set()


async def test_a_deleted_plugin_is_ignored(session: AsyncSession, current_user: User) -> None:
    await _seed_plugin(session, "stub", False, True)

    assert await disabled_plugin_names(cast(int, current_user.id), session) == set()


async def test_with_no_user_only_the_system_switch_applies(session: AsyncSession, current_user: User) -> None:
    await _seed_plugin(session, "system-off", False)
    plugin = await _seed_plugin(session, "user-off", True)
    await _seed_preference(session, cast(int, current_user.id), plugin, False)

    assert await disabled_plugin_names(None, session) == {"system-off"}


async def test_the_dependency_reuses_the_set_the_gate_left(session: AsyncSession, current_user: User) -> None:
    await _seed_plugin(session, "stub", False)
    request = Request({"type": "http", "state": {"disabled_plugins": {"from-the-gate"}}})

    assert await get_disabled_plugins(request, current_user, session) == {"from-the-gate"}


async def test_the_dependency_reads_the_switches_when_the_gate_left_none(
    session: AsyncSession, current_user: User
) -> None:
    await _seed_plugin(session, "stub", False)
    request = Request({"type": "http"})

    assert await get_disabled_plugins(request, current_user, session) == {"stub"}


def test_validation_error_never_echoes_stored_values() -> None:
    class LmsConfig(PluginConfig):
        api_url: str
        api_key: str

    with patch("sparkth.core.plugins.service.get_plugin_config_schema", return_value=LmsConfig):
        with pytest.raises(ConfigValidationError) as raised:
            PluginService.validate_user_config(Plugin(name="lms"), {"api_key": "s3cret"})

    assert "s3cret" not in str(raised.value)


def test_validation_error_names_each_field_and_problem() -> None:
    class LmsConfig(PluginConfig):
        api_url: str
        api_key: str

    with patch("sparkth.core.plugins.service.get_plugin_config_schema", return_value=LmsConfig):
        with pytest.raises(ConfigValidationError) as raised:
            PluginService.validate_user_config(Plugin(name="lms"), {})

    assert str(raised.value) == "api_url: Field required; api_key: Field required"
