"""The ``plugin`` scope: a plugin's routes are gated on ``plugin.use`` at ``plugin:<name>``.
Authored with LLM (Claude) assistance."""

from collections.abc import Callable
from typing import cast

from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.permissions import PLUGIN_USE, can, get_permission
from sparkth.lib.permissions.scopes import PLUGIN, build_scope_path
from sparkth.lib.testing import grant_global_permission, grant_permission_at_scope, make_user


async def test_user_holds_nothing_at_a_plugin_without_a_grant(session: AsyncSession) -> None:
    a = await make_user(session, "alice")
    await session.commit()
    assert await can(a, PLUGIN_USE, PLUGIN, build_scope_path(PLUGIN, "slack"), session) is False


async def test_grant_at_one_plugin_reaches_only_that_plugin(session: AsyncSession) -> None:
    a = await make_user(session, "alice")
    await grant_permission_at_scope(session, cast(int, a.id), PLUGIN_USE.name, PLUGIN, "slack")
    await session.commit()
    assert await can(a, PLUGIN_USE, PLUGIN, build_scope_path(PLUGIN, "slack"), session) is True
    assert await can(a, PLUGIN_USE, PLUGIN, build_scope_path(PLUGIN, "compose"), session) is False


async def test_global_grant_reaches_every_plugin(session: AsyncSession) -> None:
    a = await make_user(session, "alice")
    await grant_global_permission(session, cast(int, a.id), PLUGIN_USE.name)
    await session.commit()
    assert await can(a, PLUGIN_USE, PLUGIN, build_scope_path(PLUGIN, "slack"), session) is True
    assert await can(a, PLUGIN_USE, PLUGIN, build_scope_path(PLUGIN, "open-edx"), session) is True


async def test_fixed_plugin_gate(session: AsyncSession, gated_client: Callable[..., AsyncClient]) -> None:
    a = await make_user(session, "alice")
    await session.commit()
    dep = PLUGIN_USE.require_for_object(PLUGIN, "slack")
    async with gated_client(dep, a) as client:
        assert (await client.get("/probe")).status_code == 403
    await grant_permission_at_scope(session, cast(int, a.id), PLUGIN_USE.name, PLUGIN, "slack")
    await session.commit()
    async with gated_client(dep, a) as client:
        assert (await client.get("/probe")).status_code == 200


def test_feature_permissions_are_registered() -> None:
    assert get_permission("plugin.use").name == "plugin.use"
    assert get_permission("file.upload").name == "file.upload"
