"""Unit tests for PluginService."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.plugin import Plugin, UserPlugin
from app.services.plugin import PluginService


def _make_plugin(name: str = "chat", plugin_id: int = 1) -> Plugin:
    plugin = Plugin(name=name, is_core=True, config_schema={}, enabled=True)
    plugin.id = plugin_id
    return plugin


def _make_session(user_plugin: UserPlugin | None = None) -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.one_or_none.return_value = user_plugin
    session.exec.return_value = result
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_update_user_plugin_config_strips_legacy_fields() -> None:
    """Merging new config onto legacy stored config must not fail with extra_forbidden."""
    legacy_config = {
        "provider": "anthropic",
        "model": "claude-sonnet-4-20250514",
        "provider_api_key_ref": "some-ref",
        "llm_config_name": None,
        "llm_provider": None,
        "llm_model": None,
    }
    old_user_plugin = UserPlugin(user_id=1, plugin_id=1, enabled=True, config=legacy_config)
    session = _make_session(old_user_plugin)

    plugin = _make_plugin()
    service = PluginService()

    result = await service.update_user_plugin_config(
        session=session,
        user_id=1,
        plugin=plugin,
        user_config={"llm_config_id": 3},
    )

    assert result.config.get("llm_config_id") == 3
    assert "provider" not in result.config
    assert "model" not in result.config
    assert "provider_api_key_ref" not in result.config


@pytest.mark.asyncio
async def test_update_user_plugin_config_valid_config_succeeds() -> None:
    """Updating with a valid config when no prior config exists works."""
    session = _make_session(None)
    plugin = _make_plugin()
    service = PluginService()

    result = await service.update_user_plugin_config(
        session=session,
        user_id=1,
        plugin=plugin,
        user_config={"llm_config_id": 5},
    )

    assert result.config.get("llm_config_id") == 5


@pytest.mark.asyncio
async def test_update_config_revalidates_stored_model_override_against_new_provider() -> None:
    """Partial PUT changing llm_config_id must re-validate the stored llm_model_override."""
    from unittest.mock import MagicMock

    from app.models.llm import LLMConfig

    stored = {"llm_config_id": 1, "llm_model_override": "gpt-4o"}
    old_user_plugin = UserPlugin(user_id=1, plugin_id=1, enabled=True, config=stored)

    anthropic_llm = LLMConfig(
        id=2,
        user_id=1,
        name="Claude",
        provider="anthropic",
        model="claude-sonnet-4-5",
        encrypted_key="enc",
        masked_key="sk-ant-...abcd",
    )

    up_result = MagicMock()
    up_result.one_or_none.return_value = old_user_plugin

    llm_result = MagicMock()
    llm_result.first.return_value = anthropic_llm

    session = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.exec.side_effect = [up_result, llm_result]

    plugin = _make_plugin(name="slack")
    service = PluginService()

    with pytest.raises(ValueError, match="not available for provider"):
        await service.update_user_plugin_config(
            session=session,
            user_id=1,
            plugin=plugin,
            user_config={"llm_config_id": 2},
        )


# --- get_or_create_all ---------------------------------------------------------


class _FakePlugin:
    """Minimal stand-in for a loaded SparkthPlugin."""

    def __init__(self, name: str, schema: dict[str, Any]) -> None:
        self.name = name
        self._schema = schema

    def get_config_schema(self) -> dict[str, Any]:
        return self._schema


class _FakeLoader:
    def __init__(self, plugins: list[_FakePlugin]) -> None:
        self._plugins = plugins

    def get_loaded_plugins(self) -> list[tuple[str, _FakePlugin]]:
        return [(p.name, p) for p in self._plugins]


def _patch_bootstrap(session: AsyncSession, plugins: list[_FakePlugin]) -> Any:
    """Patch get_or_create_all's loader and session so it runs against the test DB.

    ``session_scope`` is replaced with a context manager yielding the test
    session, and that session's ``commit`` is aliased to ``flush`` so the test
    fixture's outer transaction can still roll the writes back.
    """

    @asynccontextmanager
    async def _scope(*_args: Any, **_kwargs: Any) -> AsyncGenerator[AsyncSession, None]:
        with patch.object(session, "commit", session.flush):
            yield session

    return (
        patch("app.services.plugin.get_plugin_loader", return_value=_FakeLoader(plugins)),
        patch("app.services.plugin.session_scope", _scope),
    )


@pytest.mark.asyncio
async def test_get_or_create_all_inserts_missing_plugins(session: AsyncSession) -> None:
    plugins = [_FakePlugin("alpha", {"type": "object"}), _FakePlugin("beta", {})]
    loader_patch, scope_patch = _patch_bootstrap(session, plugins)

    with loader_patch, scope_patch:
        await PluginService().get_or_create_all()

    rows = (await session.exec(select(Plugin).order_by(Plugin.name))).all()
    assert [r.name for r in rows] == ["alpha", "beta"]
    assert all(r.is_core and r.enabled for r in rows)
    assert {r.name: r.config_schema for r in rows} == {"alpha": {"type": "object"}, "beta": {}}


@pytest.mark.asyncio
async def test_get_or_create_all_is_idempotent(session: AsyncSession) -> None:
    plugins = [_FakePlugin("alpha", {"type": "object"})]
    loader_patch, scope_patch = _patch_bootstrap(session, plugins)

    with loader_patch, scope_patch:
        await PluginService().get_or_create_all()
        await PluginService().get_or_create_all()

    rows = (await session.exec(select(Plugin).where(Plugin.name == "alpha"))).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_get_or_create_all_updates_schema_but_preserves_enabled(session: AsyncSession) -> None:
    existing = Plugin(name="alpha", is_core=True, enabled=False, config_schema={"old": True})
    session.add(existing)
    await session.flush()

    plugins = [_FakePlugin("alpha", {"new": True})]
    loader_patch, scope_patch = _patch_bootstrap(session, plugins)

    with loader_patch, scope_patch:
        await PluginService().get_or_create_all()

    rows = (await session.exec(select(Plugin).where(Plugin.name == "alpha"))).all()
    assert len(rows) == 1
    assert rows[0].config_schema == {"new": True}
    assert rows[0].enabled is False
