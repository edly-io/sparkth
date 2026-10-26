from typing import Any, cast

import pytest
from pydantic import HttpUrl
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin, UserPlugin
from sparkth.lib.auth import bind_current_user_id
from sparkth.lib.exceptions.auth import NoAuthenticatedUser
from sparkth.lib.models import User
from sparkth.lib.plugins import (
    PluginConfig,
    PluginConfigInvalidError,
    PluginNotConfiguredError,
    load_user_plugin_config,
)


class _SampleConfig(PluginConfig):
    api_url: HttpUrl
    api_key: str


async def _seed(session: AsyncSession, owner_id: int, config: dict[str, Any]) -> None:
    plugin = Plugin(name="sample", enabled=True)
    users = [User(id=i, name="U", username=f"u{i}", email=f"u{i}@example.com", hashed_password="x") for i in (1, 2)]
    session.add_all([plugin, *users])
    await session.commit()
    session.add(UserPlugin(user_id=owner_id, plugin_id=cast(int, plugin.id), config=config))
    await session.commit()


async def test_returns_the_callers_stored_settings_typed(session: AsyncSession) -> None:
    await _seed(session, 1, {"api_url": "https://lms.example.com", "api_key": "stored-key"})
    bind_current_user_id(1)

    result = await load_user_plugin_config("sample", _SampleConfig)

    assert str(result.api_url) == "https://lms.example.com/"
    assert result.api_key == "stored-key"


async def test_another_users_settings_are_never_returned(session: AsyncSession) -> None:
    await _seed(session, 2, {"api_url": "https://lms.example.com", "api_key": "stored-key"})
    bind_current_user_id(1)

    with pytest.raises(PluginNotConfiguredError):
        await load_user_plugin_config("sample", _SampleConfig)


async def test_no_settings_raise_with_the_my_plugins_message(session: AsyncSession) -> None:
    bind_current_user_id(1)

    with pytest.raises(PluginNotConfiguredError) as exc:
        await load_user_plugin_config("sample", _SampleConfig)

    assert str(exc.value) == (
        "sample is not set up for this user. Tell them to add their sample settings on the Settings page."
    )


async def test_empty_settings_raise(session: AsyncSession) -> None:
    await _seed(session, 1, {})
    bind_current_user_id(1)

    with pytest.raises(PluginNotConfiguredError):
        await load_user_plugin_config("sample", _SampleConfig)


async def test_settings_that_fail_validation_raise_and_log_no_values(
    session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    await _seed(session, 1, {"api_url": "not-a-url", "api_key": "secret-value"})
    bind_current_user_id(1)

    with pytest.raises(PluginConfigInvalidError) as exc:
        await load_user_plugin_config("sample", _SampleConfig)

    assert str(exc.value) == (
        "The saved sample settings for this user are no longer valid. "
        "Tell them to update their sample settings on the Settings page."
    )
    assert "secret-value" not in caplog.text
    assert "not-a-url" not in caplog.text
    assert "sample" in caplog.text


async def test_no_bound_user_raises_no_authenticated_user() -> None:
    with pytest.raises(NoAuthenticatedUser):
        await load_user_plugin_config("sample", _SampleConfig)
