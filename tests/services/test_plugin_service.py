"""Unit tests for PluginService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

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
