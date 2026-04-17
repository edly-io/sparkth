"""Tests for LLMConfigService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.llm.service import LLMConfigService
from app.models.llm import LLMConfig


def _make_service() -> tuple[LLMConfigService, MagicMock, MagicMock]:
    enc = MagicMock()
    enc.encrypt.return_value = "enc-secret"
    enc.decrypt.return_value = "sk-plaintext"
    enc.mask_key.return_value = "sk-...abcd"
    cache = MagicMock()
    cache.make_key.return_value = "cache-key"
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    cache.delete = AsyncMock()
    return LLMConfigService(encryption=enc, cache=cache), enc, cache


def _make_session(result: LLMConfig | None = None) -> AsyncMock:
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.first.return_value = result
    mock_result.one_or_none.return_value = result
    mock_result.all.return_value = [result] if result else []
    session.exec.return_value = mock_result
    return session


@pytest.mark.asyncio
async def test_create_stores_encrypted_key() -> None:
    service, enc, _ = _make_service()
    session = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()

    await service.create(
        session=session,
        user_id=1,
        name="My Key",
        provider="anthropic",
        model="claude-sonnet-4-20250514",
        api_key="sk-real",
    )

    enc.encrypt.assert_called_once_with("sk-real")
    session.add.assert_called_once()
    added = session.add.call_args[0][0]
    assert added.encrypted_key == "enc-secret"
    assert added.user_id == 1
    assert added.name == "My Key"


@pytest.mark.asyncio
async def test_create_duplicate_name_raises() -> None:
    from sqlalchemy.exc import IntegrityError

    service, _, _ = _make_service()
    session = AsyncMock()
    session.flush = AsyncMock(side_effect=IntegrityError("", {}, Exception()))

    with pytest.raises(ValueError, match="name.*already exists"):
        await service.create(
            session=session,
            user_id=1,
            name="My Key",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="sk-real",
        )


@pytest.mark.asyncio
async def test_list_returns_user_configs() -> None:
    service, _, _ = _make_service()
    config = LLMConfig(
        user_id=1, name="K", provider="openai", model="gpt-4o", encrypted_key="enc", masked_key="sk-...abcd"
    )
    session = _make_session(config)

    results = await service.list(session=session, user_id=1)

    assert results == [config]


@pytest.mark.asyncio
async def test_resolve_returns_decrypted_key_and_updates_last_used() -> None:
    service, enc, cache = _make_service()
    config = LLMConfig(
        id=5, user_id=1, name="K", provider="openai", model="gpt-4o", encrypted_key="enc-abc", masked_key="sk-...abcd"
    )
    session = _make_session(config)

    result = await service.resolve(session=session, user_id=1, config_id=5)

    assert result == "sk-plaintext"
    enc.decrypt.assert_called_once_with("enc-abc")
    cache.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_cache_hit_skips_db() -> None:
    service, enc, cache = _make_service()
    cache.get = AsyncMock(return_value="enc-cached")
    session = AsyncMock()

    result = await service.resolve(session=session, user_id=1, config_id=5)

    assert result == "sk-plaintext"
    enc.decrypt.assert_called_once_with("enc-cached")
    session.exec.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_unknown_config_raises() -> None:
    service, _, _ = _make_service()
    session = _make_session(None)

    with pytest.raises(ValueError, match="LLMConfig 99 not found"):
        await service.resolve(session=session, user_id=1, config_id=99)


@pytest.mark.asyncio
async def test_resolve_empty_model_raises() -> None:
    service, _, _ = _make_service()
    config = LLMConfig(
        id=5, user_id=1, name="K", provider="openai", model="", encrypted_key="enc-abc", masked_key="sk-...abcd"
    )
    session = _make_session(config)

    with pytest.raises(ValueError, match="has no model set"):
        await service.resolve(session=session, user_id=1, config_id=5)


@pytest.mark.asyncio
async def test_delete_soft_deletes_and_returns_true() -> None:
    service, _, _ = _make_service()
    config = LLMConfig(
        id=5, user_id=1, name="K", provider="openai", model="gpt-4o", encrypted_key="enc", masked_key="sk-...abcd"
    )
    session = _make_session(config)

    result = await service.delete(session=session, user_id=1, config_id=5)

    assert result is True
    assert config.deleted_at is not None


@pytest.mark.asyncio
async def test_delete_not_found_returns_false() -> None:
    service, _, _ = _make_service()
    session = _make_session(None)

    result = await service.delete(session=session, user_id=1, config_id=99)

    assert result is False


@pytest.mark.asyncio
async def test_update_name_and_model() -> None:
    service, _, _ = _make_service()
    config = LLMConfig(
        id=5, user_id=1, name="Old", provider="openai", model="gpt-4o", encrypted_key="enc", masked_key="sk-...abcd"
    )
    session = _make_session(config)

    result = await service.update(session=session, user_id=1, config_id=5, name="New", model="gpt-4o-mini")

    assert result.name == "New"
    assert result.model == "gpt-4o-mini"
    session.add.assert_called()


@pytest.mark.asyncio
async def test_update_name_only_leaves_model_unchanged() -> None:
    service, _, _ = _make_service()
    config = LLMConfig(
        id=5, user_id=1, name="Old", provider="openai", model="gpt-4o", encrypted_key="enc", masked_key="sk-...abcd"
    )
    session = _make_session(config)

    result = await service.update(session=session, user_id=1, config_id=5, name="New")

    assert result.name == "New"
    assert result.model == "gpt-4o"


@pytest.mark.asyncio
async def test_update_not_found_raises() -> None:
    service, _, _ = _make_service()
    session = _make_session(None)

    with pytest.raises(ValueError, match="LLMConfig 99 not found"):
        await service.update(session=session, user_id=1, config_id=99, name="X")


@pytest.mark.asyncio
async def test_update_duplicate_name_raises() -> None:
    from sqlalchemy.exc import IntegrityError

    service, _, _ = _make_service()
    config = LLMConfig(
        id=5, user_id=1, name="Old", provider="openai", model="gpt-4o", encrypted_key="enc", masked_key="sk-...abcd"
    )
    session = _make_session(config)
    session.flush = AsyncMock(side_effect=IntegrityError("", {}, Exception()))

    with pytest.raises(ValueError, match="name.*already exists"):
        await service.update(session=session, user_id=1, config_id=5, name="Taken")


@pytest.mark.asyncio
async def test_rotate_key_updates_encrypted_and_masked() -> None:
    service, enc, _ = _make_service()
    config = LLMConfig(
        id=5, user_id=1, name="K", provider="openai", model="gpt-4o", encrypted_key="old-enc", masked_key="old-mask"
    )
    session = _make_session(config)

    result = await service.rotate_key(session=session, user_id=1, config_id=5, api_key="sk-new")

    enc.encrypt.assert_called_once_with("sk-new")
    assert result.encrypted_key == "enc-secret"
    assert result.masked_key == service.mask_key("sk-new")


@pytest.mark.asyncio
async def test_rotate_key_evicts_cache() -> None:
    service, _, cache = _make_service()
    config = LLMConfig(
        id=5, user_id=1, name="K", provider="openai", model="gpt-4o", encrypted_key="old-enc", masked_key="old-mask"
    )
    session = _make_session(config)

    await service.rotate_key(session=session, user_id=1, config_id=5, api_key="sk-new")

    cache.delete.assert_awaited_once_with("cache-key")


@pytest.mark.asyncio
async def test_rotate_key_not_found_raises() -> None:
    service, _, _ = _make_service()
    session = _make_session(None)

    with pytest.raises(ValueError, match="LLMConfig 99 not found"):
        await service.rotate_key(session=session, user_id=1, config_id=99, api_key="sk-new")
