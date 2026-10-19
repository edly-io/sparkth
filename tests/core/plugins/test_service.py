"""Behavioural tests for the plugin switches the service reads: which plugins are off for a user."""

from datetime import datetime, timezone
from typing import cast

from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin, UserPlugin
from sparkth.core.models.user import User
from sparkth.core.plugins.service import plugins_disabled_for_user


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

    assert await plugins_disabled_for_user(cast(int, current_user.id), session) == {"stub"}


async def test_a_plugin_the_user_switched_off_is_disabled(session: AsyncSession, current_user: User) -> None:
    user_id = cast(int, current_user.id)
    plugin = await _seed_plugin(session, "stub", True)
    await _seed_preference(session, user_id, plugin, False)

    assert await plugins_disabled_for_user(user_id, session) == {"stub"}


async def test_a_plugin_with_no_preference_is_not_disabled(session: AsyncSession, current_user: User) -> None:
    await _seed_plugin(session, "stub", True)

    assert await plugins_disabled_for_user(cast(int, current_user.id), session) == set()


async def test_a_plugin_the_user_switched_on_is_not_disabled(session: AsyncSession, current_user: User) -> None:
    user_id = cast(int, current_user.id)
    plugin = await _seed_plugin(session, "stub", True)
    await _seed_preference(session, user_id, plugin, True)

    assert await plugins_disabled_for_user(user_id, session) == set()


async def test_a_plugin_with_no_registry_row_is_not_disabled(session: AsyncSession, current_user: User) -> None:
    assert "never-registered" not in await plugins_disabled_for_user(cast(int, current_user.id), session)


async def test_another_users_preference_does_not_disable_it(session: AsyncSession, current_user: User) -> None:
    plugin = await _seed_plugin(session, "stub", True)
    await _seed_preference(session, await _seed_other_user(session), plugin, False)

    assert await plugins_disabled_for_user(cast(int, current_user.id), session) == set()


async def test_a_deleted_preference_is_ignored(session: AsyncSession, current_user: User) -> None:
    user_id = cast(int, current_user.id)
    plugin = await _seed_plugin(session, "stub", True)
    await _seed_preference(session, user_id, plugin, False, True)

    assert await plugins_disabled_for_user(user_id, session) == set()


async def test_a_deleted_plugin_is_ignored(session: AsyncSession, current_user: User) -> None:
    await _seed_plugin(session, "stub", False, True)

    assert await plugins_disabled_for_user(cast(int, current_user.id), session) == set()
