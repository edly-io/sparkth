"""Tests for SlackPluginConfigAdapter."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core_plugins.slack.adapter import SlackConfigAdapter
from app.llm.adapter import LLMConfigAdapter
from app.models import LLMConfig


@pytest.fixture
def adapter() -> SlackConfigAdapter:
    return SlackConfigAdapter()


def _session_with(config: LLMConfig | None) -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.first.return_value = config
    session.exec.return_value = result
    return session


def test_slack_adapter_extends_llm_config_plugin_adapter() -> None:
    assert issubclass(SlackConfigAdapter, LLMConfigAdapter)


@pytest.mark.asyncio
async def test_preprocess_valid_config_id_and_override_passes() -> None:
    adapter = SlackConfigAdapter()
    config = LLMConfig(
        id=7,
        user_id=2,
        name="Anthropic",
        provider="anthropic",
        model="claude-sonnet-4-5",
        encrypted_key="enc",
        masked_key="sk-ant-...abcd",
    )
    session = _session_with(config)

    result = await adapter.preprocess_config(
        session=session,
        user_id=2,
        incoming_config={"llm_config_id": 7, "llm_model_override": "claude-haiku-4-5"},
    )

    assert result["llm_config_id"] == 7
    assert result["llm_model_override"] == "claude-haiku-4-5"


@pytest.mark.asyncio
async def test_preprocess_model_override_wrong_provider_raises() -> None:
    adapter = SlackConfigAdapter()
    config = LLMConfig(
        id=7,
        user_id=2,
        name="Anthropic",
        provider="anthropic",
        model="claude-sonnet-4-5",
        encrypted_key="enc",
        masked_key="sk-ant-...abcd",
    )
    session = _session_with(config)

    with pytest.raises(ValueError, match="not available for provider"):
        await adapter.preprocess_config(
            session=session,
            user_id=2,
            incoming_config={"llm_config_id": 7, "llm_model_override": "gpt-4o"},
        )


@pytest.mark.asyncio
async def test_preprocess_override_set_without_config_id_raises() -> None:
    adapter = SlackConfigAdapter()
    session = AsyncMock()

    with pytest.raises(ValueError, match="llm_model_override requires llm_config_id"):
        await adapter.preprocess_config(
            session=session,
            user_id=2,
            incoming_config={"llm_config_id": None, "llm_model_override": "gpt-4o"},
        )


@pytest.mark.asyncio
async def test_preprocess_no_override_passes_through() -> None:
    adapter = SlackConfigAdapter()
    config = LLMConfig(
        id=7,
        user_id=2,
        name="Anthropic",
        provider="anthropic",
        model="claude-sonnet-4-5",
        encrypted_key="enc",
        masked_key="sk-ant-...abcd",
    )
    session = _session_with(config)

    result = await adapter.preprocess_config(
        session=session,
        user_id=2,
        incoming_config={"llm_config_id": 7, "bot_name": "TA Bot"},
    )

    assert result["llm_config_id"] == 7
    assert result.get("llm_model_override") is None


@pytest.mark.asyncio
async def test_preprocess_registered_in_plugin_adapters() -> None:
    from app.plugins.adapters import PLUGIN_ADAPTERS

    assert "slack" in PLUGIN_ADAPTERS
    assert isinstance(PLUGIN_ADAPTERS["slack"], SlackConfigAdapter)
