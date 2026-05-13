"""Tests for LLMConfigPluginAdapter."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.llm.adapter import LLMConfigAdapter
from app.models import LLMConfig


class ConcreteAdapter(LLMConfigAdapter):
    pass


@pytest.fixture
def adapter() -> ConcreteAdapter:
    return ConcreteAdapter()


def _session_with(config: LLMConfig | None) -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.first.return_value = config
    session.exec.return_value = result
    return session


@pytest.mark.asyncio
async def test_preprocess_valid_llm_config_id_passes_through() -> None:
    adapter = ConcreteAdapter()
    config = LLMConfig(
        id=5, user_id=1, name="K", provider="openai", model="gpt-4o", encrypted_key="enc", masked_key="sk-...abcd"
    )
    session = _session_with(config)

    result = await adapter.preprocess_config(
        session=session,
        user_id=1,
        incoming_config={"llm_config_id": 5, "other_field": "value"},
    )

    assert result == {"llm_config_id": 5, "other_field": "value"}


@pytest.mark.asyncio
async def test_preprocess_unknown_llm_config_id_raises() -> None:
    adapter = ConcreteAdapter()
    session = _session_with(None)

    with pytest.raises(ValueError, match="llm_config_id"):
        await adapter.preprocess_config(
            session=session,
            user_id=1,
            incoming_config={"llm_config_id": 999},
        )


@pytest.mark.asyncio
async def test_preprocess_string_llm_config_id_is_coerced() -> None:
    adapter = ConcreteAdapter()
    config = LLMConfig(
        id=5, user_id=1, name="K", provider="openai", model="gpt-4o", encrypted_key="enc", masked_key="sk-...abcd"
    )
    session = _session_with(config)

    result = await adapter.preprocess_config(
        session=session,
        user_id=1,
        incoming_config={"llm_config_id": "5"},
    )

    assert result["llm_config_id"] == 5


@pytest.mark.asyncio
async def test_preprocess_non_numeric_llm_config_id_raises() -> None:
    adapter = ConcreteAdapter()
    session = AsyncMock()

    with pytest.raises(ValueError, match="llm_config_id"):
        await adapter.preprocess_config(
            session=session,
            user_id=1,
            incoming_config={"llm_config_id": "not-a-number"},
        )


@pytest.mark.asyncio
async def test_postprocess_string_config_id_resolves() -> None:
    adapter = ConcreteAdapter()
    config = LLMConfig(
        id=5,
        user_id=1,
        name="My Claude",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        encrypted_key="enc",
        masked_key="sk-...abcd",
    )
    session = _session_with(config)

    result = await adapter.postprocess_config(
        session=session,
        user_id=1,
        stored_config={"llm_config_id": "5"},
    )

    assert result["llm_config_name"] == "My Claude"
    assert result["llm_provider"] == "anthropic"


@pytest.mark.asyncio
async def test_preprocess_none_llm_config_id_passes_through() -> None:
    adapter = ConcreteAdapter()
    session = AsyncMock()

    result = await adapter.preprocess_config(
        session=session,
        user_id=1,
        incoming_config={"llm_config_id": None, "bot_name": "TA Bot"},
    )

    assert result == {"llm_config_id": None, "bot_name": "TA Bot"}
    session.exec.assert_not_awaited()


@pytest.mark.asyncio
async def test_postprocess_resolves_config_name_and_provider() -> None:
    adapter = ConcreteAdapter()
    config = LLMConfig(
        id=5,
        user_id=1,
        name="My Claude",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        encrypted_key="enc",
        masked_key="sk-...abcd",
    )
    session = _session_with(config)

    result = await adapter.postprocess_config(
        session=session,
        user_id=1,
        stored_config={"llm_config_id": 5, "llm_model_override": None},
    )

    assert result["llm_config_id"] == 5
    assert result["llm_config_name"] == "My Claude"
    assert result["llm_provider"] == "anthropic"
    assert result["llm_model"] == "claude-sonnet-4-20250514"


@pytest.mark.asyncio
async def test_preprocess_deactivated_llm_config_id_raises() -> None:
    adapter = ConcreteAdapter()
    config = LLMConfig(
        id=5,
        user_id=1,
        name="K",
        provider="openai",
        model="gpt-4o",
        encrypted_key="enc",
        masked_key="sk-...abcd",
        is_active=False,
    )
    session = _session_with(config)

    with pytest.raises(ValueError, match="deactivated"):
        await adapter.preprocess_config(
            session=session,
            user_id=1,
            incoming_config={"llm_config_id": 5},
        )


@pytest.mark.asyncio
async def test_postprocess_none_id_returns_null_fields() -> None:
    adapter = ConcreteAdapter()
    session = AsyncMock()

    result = await adapter.postprocess_config(
        session=session,
        user_id=1,
        stored_config={"llm_config_id": None},
    )

    assert result["llm_config_id"] is None
    assert result["llm_config_name"] is None
    assert result["llm_provider"] is None
    assert result["llm_model"] is None
    session.exec.assert_not_awaited()


@pytest.mark.asyncio
async def test_preprocess_model_override_without_config_id_raises() -> None:
    adapter = ConcreteAdapter()
    session = AsyncMock()

    with pytest.raises(ValueError, match="llm_model_override requires llm_config_id"):
        await adapter.preprocess_config(
            session=session,
            user_id=1,
            incoming_config={"llm_config_id": None, "llm_model_override": "gpt-4o"},
        )


@pytest.mark.asyncio
async def test_preprocess_valid_model_override_passes_through() -> None:
    adapter = ConcreteAdapter()
    config = LLMConfig(
        id=5, user_id=1, name="K", provider="openai", model="gpt-4o", encrypted_key="enc", masked_key="sk-...abcd"
    )
    session = _session_with(config)

    result = await adapter.preprocess_config(
        session=session,
        user_id=1,
        incoming_config={"llm_config_id": 5, "llm_model_override": "gpt-4o-mini"},
    )

    assert result["llm_model_override"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_preprocess_invalid_model_override_raises() -> None:
    adapter = ConcreteAdapter()
    config = LLMConfig(
        id=5, user_id=1, name="K", provider="openai", model="gpt-4o", encrypted_key="enc", masked_key="sk-...abcd"
    )
    session = _session_with(config)

    with pytest.raises(ValueError, match="not available for provider"):
        await adapter.preprocess_config(
            session=session,
            user_id=1,
            incoming_config={"llm_config_id": 5, "llm_model_override": "claude-sonnet-4-5"},
        )


@pytest.mark.asyncio
async def test_preprocess_none_model_override_with_valid_config_id_passes_through() -> None:
    adapter = ConcreteAdapter()
    config = LLMConfig(
        id=5, user_id=1, name="K", provider="openai", model="gpt-4o", encrypted_key="enc", masked_key="sk-...abcd"
    )
    session = _session_with(config)

    result = await adapter.preprocess_config(
        session=session,
        user_id=1,
        incoming_config={"llm_config_id": 5, "llm_model_override": None},
    )

    assert result["llm_model_override"] is None
