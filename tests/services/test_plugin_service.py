"""Unit tests for PluginService."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin, UserPlugin
from sparkth.core.plugins.service import PluginService


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

    from sparkth.core.models.llm import LLMConfig

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
        self.schema = schema


class _FakeLoader:
    def __init__(self, plugins: list[_FakePlugin]) -> None:
        self._plugins = plugins

    def get_loaded_plugins(self) -> list[tuple[str, _FakePlugin]]:
        return [(p.name, p) for p in self._plugins]


def _fake_config_class(schema: dict[str, Any]) -> type:
    """Build a stand-in config class whose ``model_json_schema()`` returns ``schema``."""

    class _FakeConfig:
        @classmethod
        def model_json_schema(cls) -> dict[str, Any]:
            return schema

    return _FakeConfig


def _patch_bootstrap(plugins: list[_FakePlugin]) -> Any:
    """Patch get_or_create_all's loader and config resolver.

    ``get_plugin_config_schema`` is patched to resolve each fake plugin's schema by
    name (mirroring the real ``CONFIG_SCHEMAS`` hook lookup). ``session_scope`` is left
    untouched: it is engine-backed, so ``get_or_create_all`` writes to the same
    in-memory test database the ``session`` fixture reads from.
    """
    schemas_by_name = {p.name: _fake_config_class(p.schema) for p in plugins}

    return (
        patch("sparkth.core.plugins.service.get_plugin_loader", return_value=_FakeLoader(plugins)),
        patch("sparkth.core.plugins.service.get_plugin_config_schema", side_effect=schemas_by_name.get),
    )


@pytest.mark.asyncio
async def test_get_or_create_all_inserts_missing_plugins(session: AsyncSession) -> None:
    plugins = [_FakePlugin("alpha", {"type": "object"}), _FakePlugin("beta", {})]
    loader_patch, config_patch = _patch_bootstrap(plugins)

    with loader_patch, config_patch:
        await PluginService().get_or_create_all()

    rows = (await session.exec(select(Plugin).order_by(Plugin.name))).all()
    assert [r.name for r in rows] == ["alpha", "beta"]
    assert all(r.is_core and r.enabled for r in rows)
    assert {r.name: r.config_schema for r in rows} == {"alpha": {"type": "object"}, "beta": {}}


@pytest.mark.asyncio
async def test_get_or_create_all_is_idempotent(session: AsyncSession) -> None:
    plugins = [_FakePlugin("alpha", {"type": "object"})]
    loader_patch, config_patch = _patch_bootstrap(plugins)

    with loader_patch, config_patch:
        await PluginService().get_or_create_all()
        await PluginService().get_or_create_all()

    rows = (await session.exec(select(Plugin).where(Plugin.name == "alpha"))).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_get_or_create_all_updates_schema_but_preserves_enabled(session: AsyncSession) -> None:
    existing = Plugin(name="alpha", is_core=True, enabled=False, config_schema={"old": True})
    session.add(existing)
    # Commit so get_or_create_all's own session sees the seeded row on the shared
    # in-memory connection.
    await session.commit()

    plugins = [_FakePlugin("alpha", {"new": True})]
    loader_patch, config_patch = _patch_bootstrap(plugins)

    with loader_patch, config_patch:
        await PluginService().get_or_create_all()

    # get_or_create_all updated the row on its own session; drop our identity-map copy
    # so the re-query reflects the committed change.
    session.expire_all()
    rows = (await session.exec(select(Plugin).where(Plugin.name == "alpha"))).all()
    assert len(rows) == 1
    assert rows[0].config_schema == {"new": True}
    assert rows[0].enabled is False
