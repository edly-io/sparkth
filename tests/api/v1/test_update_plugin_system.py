from typing import cast

from fastapi import status
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin
from sparkth.core.models.user import User
from sparkth.core.plugins.service import disabled_plugin_names
from sparkth.lib.permissions.scopes import GLOBAL, PLUGIN
from sparkth.lib.testing import AuditEventsFetcher, grant_permission_at_scope

URL = "/api/v1/plugins/{name}/system"
PLUGIN_MANAGE_NAME = "plugin.manage"


async def grant_manage(session: AsyncSession, user: User, plugin_name: str | None) -> None:
    """Grant ``plugin.manage`` at the plugin scope of ``plugin_name``, or globally when it is ``None``."""
    scope, scope_object_id = (GLOBAL, None) if plugin_name is None else (PLUGIN, plugin_name)
    await grant_permission_at_scope(session, cast(int, user.id), PLUGIN_MANAGE_NAME, scope, scope_object_id)
    await session.commit()


async def get_system_enabled(session: AsyncSession, plugin_name: str) -> bool:
    """Read the plugin's system-wide switch as committed, not as cached in the session."""
    plugin = (await session.exec(select(Plugin).where(Plugin.name == plugin_name))).one()
    await session.refresh(plugin)
    return plugin.enabled


async def test_a_holder_switches_a_plugin_off_for_everyone(
    client: AsyncClient, plugin_preferences: User, session: AsyncSession
) -> None:
    await grant_manage(session, plugin_preferences, "plugin_a")

    response = await client.patch(URL.format(name="plugin_a"), json={"enabled": False})

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"plugin_name": "plugin_a", "system_enabled": False}
    assert "plugin_a" in await disabled_plugin_names(None, session)


async def test_a_holder_switches_a_plugin_back_on(
    client: AsyncClient, plugin_preferences: User, session: AsyncSession
) -> None:
    await grant_manage(session, plugin_preferences, "disabled_plugin")

    response = await client.patch(URL.format(name="disabled_plugin"), json={"enabled": True})

    assert response.status_code == status.HTTP_200_OK
    assert "disabled_plugin" not in await disabled_plugin_names(None, session)


async def test_a_caller_without_the_permission_is_refused(
    client: AsyncClient, plugin_preferences: User, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    await session.commit()

    response = await client.patch(URL.format(name="plugin_a"), json={"enabled": False})

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert await get_system_enabled(session, "plugin_a") is True
    last = (await audit_events())[-1]
    assert (last.category, last.action, last.target_id) == ("permission", "denied", PLUGIN_MANAGE_NAME)


async def test_a_holder_at_one_plugin_cannot_switch_another(
    client: AsyncClient, plugin_preferences: User, session: AsyncSession
) -> None:
    await grant_manage(session, plugin_preferences, "plugin_a")

    response = await client.patch(URL.format(name="plugin_b"), json={"enabled": False})

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert await get_system_enabled(session, "plugin_b") is True


async def test_an_unknown_plugin_is_not_found_for_a_global_holder(
    client: AsyncClient, plugin_preferences: User, session: AsyncSession
) -> None:
    await grant_manage(session, plugin_preferences, None)

    response = await client.patch(URL.format(name="nope"), json={"enabled": False})

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_an_unknown_plugin_is_refused_without_the_permission(
    client: AsyncClient, plugin_preferences: User, session: AsyncSession
) -> None:
    await session.commit()

    response = await client.patch(URL.format(name="nope"), json={"enabled": False})

    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_the_switch_is_recorded_against_the_caller(
    client: AsyncClient, plugin_preferences: User, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    await grant_manage(session, plugin_preferences, "plugin_a")

    response = await client.patch(URL.format(name="plugin_a"), json={"enabled": False})

    assert response.status_code == status.HTTP_200_OK
    [event] = [e for e in await audit_events() if e.category == "plugin"]
    assert (event.action, event.actor_id) == ("system_enabled_changed", str(plugin_preferences.id))


async def test_switching_off_and_on_keeps_the_callers_preference_and_config(
    client: AsyncClient, plugin_preferences: User, session: AsyncSession
) -> None:
    plugin_url = "/api/v1/plugins/configured_plugin_disabled"
    await grant_manage(session, plugin_preferences, "configured_plugin_disabled")
    before = await client.get(plugin_url)
    assert before.status_code == status.HTTP_200_OK
    assert before.json()["enabled"] is False

    off = await client.patch(URL.format(name="configured_plugin_disabled"), json={"enabled": False})
    on = await client.patch(URL.format(name="configured_plugin_disabled"), json={"enabled": True})
    after = await client.get(plugin_url)

    assert (off.status_code, on.status_code) == (status.HTTP_200_OK, status.HTTP_200_OK)
    assert after.json()["enabled"] is False
    assert after.json()["config"] == before.json()["config"]


async def test_a_body_without_enabled_is_rejected(
    client: AsyncClient, plugin_preferences: User, session: AsyncSession
) -> None:
    await grant_manage(session, plugin_preferences, "plugin_a")

    response = await client.patch(URL.format(name="plugin_a"), json={})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
