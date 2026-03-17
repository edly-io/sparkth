from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core_plugins.chat.plugin_adapter import ChatPluginConfigAdapter


@pytest.fixture
def adapter() -> ChatPluginConfigAdapter:
    return ChatPluginConfigAdapter()


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    no_result = MagicMock()
    no_result.one_or_none.return_value = None
    session.exec.return_value = no_result
    return session


@pytest.fixture
def mock_chat_service() -> MagicMock:
    service = MagicMock()
    service.create_api_key = AsyncMock()
    return service


@pytest.fixture
def patch_chat_service(mock_chat_service: MagicMock) -> Generator[MagicMock, None, None]:
    """Patches ChatService construction and its dependencies."""
    with (
        patch("app.core_plugins.chat.plugin_adapter.get_chat_system_config", return_value=MagicMock()),
        patch("app.core_plugins.chat.plugin_adapter.get_encryption_service", return_value=MagicMock()),
        patch("app.core_plugins.chat.plugin_adapter.get_cache_service", return_value=MagicMock()),
        patch("app.core_plugins.chat.plugin_adapter.ChatService", return_value=mock_chat_service),
    ):
        yield mock_chat_service


class TestPreprocessConfig:
    async def test_extracts_api_key_and_stores_ref(
        self,
        adapter: ChatPluginConfigAdapter,
        mock_session: AsyncMock,
        patch_chat_service: MagicMock,
    ) -> None:
        db_key = MagicMock(id=42)
        patch_chat_service.create_api_key.return_value = db_key

        result = await adapter.preprocess_config(
            session=mock_session,
            user_id=1,
            incoming_config={"api_key": "sk-secret", "provider": "openai"},
        )

        assert "api_key" not in result
        assert result["provider_api_key_ref"] == 42
        patch_chat_service.create_api_key.assert_awaited_once_with(
            session=mock_session,
            user_id=1,
            provider="openai",
            api_key="sk-secret",
        )

    async def test_no_api_key_returns_config_unchanged(
        self,
        adapter: ChatPluginConfigAdapter,
        mock_session: AsyncMock,
        patch_chat_service: MagicMock,
    ) -> None:
        incoming = {"provider": "openai", "temperature": 0.7}

        result = await adapter.preprocess_config(
            session=mock_session,
            user_id=1,
            incoming_config=incoming,
        )

        assert result == {"provider": "openai", "temperature": 0.7}
        patch_chat_service.create_api_key.assert_not_awaited()

    async def test_api_key_without_provider_raises(
        self,
        adapter: ChatPluginConfigAdapter,
        mock_session: AsyncMock,
        patch_chat_service: MagicMock,
    ) -> None:
        with pytest.raises(ValueError, match="Provider is required when api_key is provided"):
            await adapter.preprocess_config(
                session=mock_session,
                user_id=1,
                incoming_config={"api_key": "sk-secret"},
            )

        patch_chat_service.create_api_key.assert_not_awaited()

    async def test_preserves_other_config_fields(
        self,
        adapter: ChatPluginConfigAdapter,
        mock_session: AsyncMock,
        patch_chat_service: MagicMock,
    ) -> None:
        db_key = MagicMock(id=7)
        patch_chat_service.create_api_key.return_value = db_key

        result = await adapter.preprocess_config(
            session=mock_session,
            user_id=1,
            incoming_config={"api_key": "sk-secret", "provider": "openai", "temperature": 0.5},
        )

        assert result["provider"] == "openai"
        assert result["temperature"] == 0.5

    async def test_masked_key_roundtrip_preserves_existing_ref(
        self,
        adapter: ChatPluginConfigAdapter,
        mock_session: AsyncMock,
        patch_chat_service: MagicMock,
    ) -> None:
        """
        When the frontend echoes back the masked display value (e.g. 'sk-****abcd'),
        preprocess_config must NOT re-encrypt it.  The existing provider_api_key_ref
        should be preserved and create_api_key must never be called.
        """
        existing_key = MagicMock(id=5, masked_key="sk-****abcd")
        existing_result = MagicMock()
        existing_result.one_or_none.return_value = existing_key
        mock_session.exec.return_value = existing_result

        result = await adapter.preprocess_config(
            session=mock_session,
            user_id=1,
            incoming_config={"api_key": "sk-****abcd", "provider": "anthropic"},
        )

        assert result["provider_api_key_ref"] == 5
        assert "api_key" not in result
        patch_chat_service.create_api_key.assert_not_awaited()

    async def test_no_api_key_with_existing_key_preserves_ref(
        self,
        adapter: ChatPluginConfigAdapter,
        mock_session: AsyncMock,
        patch_chat_service: MagicMock,
    ) -> None:
        """
        When api_key is omitted (frontend omitted it intentionally), the existing
        provider_api_key_ref must be carried forward so the stored key is not lost.
        """
        existing_key = MagicMock(id=11, masked_key="sk-****zzzz")
        existing_result = MagicMock()
        existing_result.one_or_none.return_value = existing_key
        mock_session.exec.return_value = existing_result

        result = await adapter.preprocess_config(
            session=mock_session,
            user_id=1,
            incoming_config={"provider": "openai", "model": "gpt-4o"},
        )

        assert result["provider_api_key_ref"] == 11
        assert "api_key" not in result
        patch_chat_service.create_api_key.assert_not_awaited()

    async def test_no_api_key_without_existing_key_returns_config_unchanged(
        self,
        adapter: ChatPluginConfigAdapter,
        mock_session: AsyncMock,
        patch_chat_service: MagicMock,
    ) -> None:
        """
        When api_key is absent AND there is no existing stored key,
        the config is returned as-is without a provider_api_key_ref.
        """

        result = await adapter.preprocess_config(
            session=mock_session,
            user_id=1,
            incoming_config={"provider": "openai", "model": "gpt-4o"},
        )

        assert "provider_api_key_ref" not in result
        patch_chat_service.create_api_key.assert_not_awaited()

    async def test_new_real_key_overwrites_existing(
        self,
        adapter: ChatPluginConfigAdapter,
        mock_session: AsyncMock,
        patch_chat_service: MagicMock,
    ) -> None:
        """
        When a genuinely new (non-masked) key is provided, create_api_key is called
        and the new ref replaces the old one, even if an existing key is present.
        """
        existing_key = MagicMock(id=5, masked_key="sk-****abcd")
        existing_result = MagicMock()
        existing_result.one_or_none.return_value = existing_key
        mock_session.exec.return_value = existing_result

        new_db_key = MagicMock(id=99)
        patch_chat_service.create_api_key.return_value = new_db_key

        result = await adapter.preprocess_config(
            session=mock_session,
            user_id=1,
            incoming_config={"api_key": "sk-brand-new-key", "provider": "anthropic"},
        )

        assert result["provider_api_key_ref"] == 99
        patch_chat_service.create_api_key.assert_awaited_once_with(
            session=mock_session,
            user_id=1,
            provider="anthropic",
            api_key="sk-brand-new-key",
        )


class TestPostprocessConfig:
    async def test_replaces_ref_with_masked_key(
        self,
        adapter: ChatPluginConfigAdapter,
        mock_session: AsyncMock,
    ) -> None:
        db_key = MagicMock(masked_key="sk-...abcd")
        mock_result = MagicMock()
        mock_result.one_or_none.return_value = db_key
        mock_session.exec.return_value = mock_result

        result = await adapter.postprocess_config(
            session=mock_session,
            user_id=1,
            stored_config={"provider": "openai", "provider_api_key_ref": 42},
        )

        assert "provider_api_key_ref" not in result
        assert result["api_key"] == "sk-...abcd"
        assert result["provider"] == "openai"

    async def test_ref_not_found_returns_none_api_key(
        self,
        adapter: ChatPluginConfigAdapter,
        mock_session: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.one_or_none.return_value = None
        mock_session.exec.return_value = mock_result

        result = await adapter.postprocess_config(
            session=mock_session,
            user_id=1,
            stored_config={"provider": "openai", "provider_api_key_ref": 99},
        )

        assert result["api_key"] is None

    async def test_no_ref_returns_none_api_key_without_db_call(
        self,
        adapter: ChatPluginConfigAdapter,
        mock_session: AsyncMock,
    ) -> None:
        result = await adapter.postprocess_config(
            session=mock_session,
            user_id=1,
            stored_config={"provider": "openai"},
        )

        assert result["api_key"] is None
        mock_session.exec.assert_not_awaited()

    async def test_does_not_mutate_stored_config(
        self,
        adapter: ChatPluginConfigAdapter,
        mock_session: AsyncMock,
    ) -> None:
        db_key = MagicMock(masked_key="sk-...abcd")
        mock_result = MagicMock()
        mock_result.one_or_none.return_value = db_key
        mock_session.exec.return_value = mock_result

        stored = {"provider": "openai", "provider_api_key_ref": 42}

        await adapter.postprocess_config(
            session=mock_session,
            user_id=1,
            stored_config=stored,
        )

        assert "provider_api_key_ref" in stored
        assert "api_key" not in stored
