"""Tests for ChatPluginConfigAdapter (now delegates to LLMConfigPluginAdapter)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core_plugins.chat.plugin_adapter import ChatPluginConfigAdapter
from app.models import LLMConfig


@pytest.fixture
def adapter() -> ChatPluginConfigAdapter:
    return ChatPluginConfigAdapter()


def _session_with(config: LLMConfig | None) -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.first.return_value = config
    session.exec.return_value = result
    return session


@pytest.mark.asyncio
async def test_preprocess_valid_llm_config_id_passes_through(adapter: ChatPluginConfigAdapter) -> None:
    config = LLMConfig(
        id=3,
        user_id=1,
        name="K",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        encrypted_key="enc",
        masked_key="sk-...abcd",
    )
    session = _session_with(config)

    result = await adapter.preprocess_config(
        session=session,
        user_id=1,
        incoming_config={"llm_config_id": 3, "temperature": 0.7},
    )

    assert result == {"llm_config_id": 3, "temperature": 0.7}


@pytest.mark.asyncio
async def test_preprocess_unknown_llm_config_id_raises(adapter: ChatPluginConfigAdapter) -> None:
    session = _session_with(None)

    with pytest.raises(ValueError, match="llm_config_id"):
        await adapter.preprocess_config(
            session=session,
            user_id=1,
            incoming_config={"llm_config_id": 999},
        )


@pytest.mark.asyncio
async def test_postprocess_resolves_llm_fields(adapter: ChatPluginConfigAdapter) -> None:
    config = LLMConfig(
        id=3,
        user_id=1,
        name="My Key",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        encrypted_key="enc",
        masked_key="sk-...abcd",
    )
    session = _session_with(config)

    result = await adapter.postprocess_config(
        session=session,
        user_id=1,
        stored_config={"llm_config_id": 3},
    )

    assert result["llm_config_name"] == "My Key"
    assert result["llm_provider"] == "anthropic"
    assert result["llm_model"] == "claude-sonnet-4-20250514"
