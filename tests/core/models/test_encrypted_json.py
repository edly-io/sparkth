import logging
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.dialects import sqlite
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.encryption import EncryptionService
from sparkth.core.models.plugin import Plugin, UserPlugin
from sparkth.core.models.types import EncryptedJSON
from sparkth.core.models.user import User
from sparkth.core.plugins.service import PluginService


async def _stored(session: AsyncSession, user: User, config: dict[str, str]) -> UserPlugin:
    plugin = Plugin(name="encrypted_plugin")
    session.add(plugin)
    await session.flush()
    user_plugin = UserPlugin(user_id=cast(int, user.id), plugin_id=cast(int, plugin.id), config=config)
    session.add(user_plugin)
    await session.flush()
    return user_plugin


async def test_config_is_not_stored_readable(session: AsyncSession, current_user: User) -> None:
    user_plugin = await _stored(session, current_user, {"api_key": "s3cret"})

    connection = await session.connection()
    result = await connection.execute(text("SELECT config FROM user_plugins WHERE id = :id"), {"id": user_plugin.id})
    raw = result.scalar_one()

    assert "s3cret" not in raw
    assert "api_key" not in raw


async def test_config_loads_back_as_saved(session: AsyncSession, current_user: User) -> None:
    user_plugin = await _stored(session, current_user, {"api_key": "s3cret", "api_url": "https://lms.example.com"})
    session.expunge_all()

    loaded = await session.get(UserPlugin, user_plugin.id)

    assert loaded is not None
    assert loaded.config == {"api_key": "s3cret", "api_url": "https://lms.example.com"}


def test_a_config_that_will_not_decrypt_loads_empty(caplog: pytest.LogCaptureFixture) -> None:
    token = EncryptionService(EncryptionService.generate_key()).encrypt('{"api_key": "s3cret"}')

    with caplog.at_level(logging.ERROR):
        assert EncryptedJSON().process_result_value(token, sqlite.dialect()) == {}
    assert "could not be decrypted" in caplog.text


async def test_one_unreadable_config_leaves_the_others_listed(session: AsyncSession, current_user: User) -> None:
    await _stored(session, current_user, {"api_key": "s3cret"})
    unreadable_plugin = Plugin(name="unreadable_plugin")
    session.add(unreadable_plugin)
    await session.flush()
    unreadable = UserPlugin(user_id=cast(int, current_user.id), plugin_id=cast(int, unreadable_plugin.id))
    session.add(unreadable)
    await session.flush()
    token = EncryptionService(EncryptionService.generate_key()).encrypt('{"api_key": "lost"}')
    connection = await session.connection()
    await connection.execute(
        text("UPDATE user_plugins SET config = :config WHERE id = :id"), {"config": token, "id": unreadable.id}
    )
    session.expunge_all()

    plugins = await PluginService().get_user_plugin_map(session, current_user.id)

    assert plugins["encrypted_plugin"].config == {"api_key": "s3cret"}
    assert plugins["unreadable_plugin"].config == {}
