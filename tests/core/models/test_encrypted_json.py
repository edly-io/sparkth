from typing import cast

import pytest
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.encryption import EncryptionService
from sparkth.core.models.plugin import Plugin, UserPlugin
from sparkth.core.models.types import EncryptedJSON
from sparkth.core.models.user import User


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


def test_wrong_key_raises() -> None:
    other_key = EncryptionService.generate_key()
    token = EncryptionService(other_key).encrypt('{"api_key": "s3cret"}')

    with pytest.raises(ValueError):
        EncryptedJSON().process_result_value(token, dialect=None)  # type: ignore[arg-type]
