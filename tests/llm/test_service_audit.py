"""Every LLM config lifecycle step, including a decrypted read of the stored
API key, leaves an audit row that never carries key material."""

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.audit.models import AuditEvent
from sparkth.lib.testing import AuditEventsFetcher
from sparkth.llm.service import LLMConfigService

PLAINTEXT = "sk-plaintext-secret-1234"
ROTATED = "sk-rotated-secret-5678"


@pytest.fixture
def service() -> LLMConfigService:
    enc = MagicMock()
    enc.encrypt.side_effect = lambda key: f"enc:{key}"
    enc.decrypt.side_effect = lambda blob: blob.removeprefix("enc:")
    cache = MagicMock()
    cache.make_key.return_value = "cache-key"
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    cache.delete = AsyncMock()
    return LLMConfigService(encryption=enc, cache=cache)


def _assert_no_key_material(event: AuditEvent) -> None:
    text = event.canonical_bytes.decode()
    assert PLAINTEXT not in text
    assert ROTATED not in text
    assert "enc:" not in text


async def test_create_records_created_event(
    service: LLMConfigService, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    config = await service.create(session, user_id=1, name="main", provider="OpenAI", model="gpt-4o", api_key=PLAINTEXT)
    await session.commit()

    (event,) = await audit_events()
    assert (event.category, event.action) == ("llm_config", "created")
    assert event.outcome == "success"
    assert event.target_type == "llm_config"
    assert event.target_id == str(config.id)
    assert event.new_values == {"name": "main", "provider": "openai", "model": "gpt-4o"}
    _assert_no_key_material(event)


async def test_update_records_before_and_after(
    service: LLMConfigService, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    config = await service.create(session, user_id=1, name="main", provider="openai", model="gpt-4o", api_key=PLAINTEXT)
    assert config.id is not None
    await service.update(session, user_id=1, config_id=config.id, name="renamed", model="gpt-4o-mini")
    await session.commit()

    _, event = await audit_events()
    assert (event.category, event.action) == ("llm_config", "updated")
    assert event.old_values == {"name": "main", "model": "gpt-4o", "is_active": True}
    assert event.new_values == {"name": "renamed", "model": "gpt-4o-mini", "is_active": True}


async def test_set_active_records_update(
    service: LLMConfigService, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    config = await service.create(session, user_id=1, name="main", provider="openai", model="gpt-4o", api_key=PLAINTEXT)
    assert config.id is not None
    await service.set_active(session, user_id=1, config_id=config.id, is_active=False)
    await session.commit()

    _, event = await audit_events()
    assert event.action == "updated"
    assert event.old_values == {"name": "main", "model": "gpt-4o", "is_active": True}
    assert event.new_values == {"name": "main", "model": "gpt-4o", "is_active": False}


async def test_rotate_key_records_rotation_without_key_material(
    service: LLMConfigService, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    config = await service.create(session, user_id=1, name="main", provider="openai", model="gpt-4o", api_key=PLAINTEXT)
    assert config.id is not None
    await service.rotate_key(session, user_id=1, config_id=config.id, api_key=ROTATED)
    await session.commit()

    _, event = await audit_events()
    assert (event.category, event.action) == ("llm_config", "key_rotated")
    assert event.target_id == str(config.id)
    assert event.old_values == {"masked_key": "sk-****1234"}
    assert event.new_values == {"masked_key": "sk-****5678"}
    _assert_no_key_material(event)


async def test_delete_records_deleted_event(
    service: LLMConfigService, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    config = await service.create(session, user_id=1, name="main", provider="openai", model="gpt-4o", api_key=PLAINTEXT)
    assert config.id is not None
    assert await service.delete(session, user_id=1, config_id=config.id) is True
    await session.commit()

    _, event = await audit_events()
    assert (event.category, event.action) == ("llm_config", "deleted")
    assert event.target_id == str(config.id)
    assert event.old_values == {"name": "main", "provider": "openai", "model": "gpt-4o"}


async def test_missing_config_delete_records_nothing(
    service: LLMConfigService, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    assert await service.delete(session, user_id=1, config_id=999) is False
    assert await audit_events() == []


async def test_resolve_records_key_read_on_cold_and_cached_paths(
    service: LLMConfigService, session: AsyncSession, audit_events: AuditEventsFetcher
) -> None:
    config = await service.create(session, user_id=1, name="main", provider="openai", model="gpt-4o", api_key=PLAINTEXT)
    assert config.id is not None

    _, key = await service.resolve(session, user_id=1, config_id=config.id)
    assert key == PLAINTEXT
    cast(AsyncMock, service.cache.get).return_value = config.encrypted_key
    _, key = await service.resolve(session, user_id=1, config_id=config.id)
    assert key == PLAINTEXT
    await session.commit()

    _, cold, cached = await audit_events()
    for event in (cold, cached):
        assert (event.category, event.action) == ("llm_config", "key_read")
        assert event.outcome == "success"
        assert event.target_id == str(config.id)
        assert event.old_values is None and event.new_values is None
        _assert_no_key_material(event)
