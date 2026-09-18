"""Plugin configuration changes are audited by key name only: config values
are credentials more often than not, so no value ever reaches the record."""

from collections.abc import Iterator
from unittest.mock import patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin
from sparkth.core.plugins.service import PluginService
from sparkth.lib.testing import AuditEventsFetcher

SECRET = "lms-p4ssw0rd"


@pytest.fixture
async def plugin(session: AsyncSession) -> Plugin:
    plugin = Plugin(name="audited_plugin", is_core=True, enabled=True)
    session.add(plugin)
    await session.flush()
    return plugin


@pytest.fixture
def passthrough_validation() -> Iterator[None]:
    with patch.object(PluginService, "validate_user_config", side_effect=lambda plugin, config: config):
        yield


async def test_create_user_plugin_records_config_keys_only(
    session: AsyncSession, plugin: Plugin, audit_events: AuditEventsFetcher
) -> None:
    assert plugin.id is not None
    user_plugin = await PluginService().create_user_plugin(
        session, 1, plugin.id, {"url": "https://x", "lms_password": SECRET}
    )

    (event,) = await audit_events()
    assert (event.category, event.action) == ("user_plugin", "config_created")
    assert event.outcome == "success"
    assert event.target_type == "user_plugin"
    assert event.target_id == str(user_plugin.id)
    assert event.new_values == {"plugin": "audited_plugin", "keys": ["lms_password", "url"]}
    assert SECRET not in event.canonical_bytes.decode()


async def test_update_user_plugin_config_records_old_and_new_keys(
    session: AsyncSession, plugin: Plugin, audit_events: AuditEventsFetcher, passthrough_validation: None
) -> None:
    assert plugin.id is not None
    service = PluginService()
    await service.create_user_plugin(session, 1, plugin.id, {"url": "https://x"})
    await service.update_user_plugin_config(session, 1, plugin, {"lms_password": SECRET})
    await session.commit()

    _, event = await audit_events()
    assert (event.category, event.action) == ("user_plugin", "config_updated")
    assert event.old_values == {"plugin": "audited_plugin", "keys": ["url"]}
    assert event.new_values == {"plugin": "audited_plugin", "keys": ["lms_password", "url"]}
    assert SECRET not in event.canonical_bytes.decode()


async def test_update_enabled_records_transition(
    session: AsyncSession, plugin: Plugin, audit_events: AuditEventsFetcher
) -> None:
    assert plugin.id is not None
    user_plugin = await PluginService().update_user_plugin_enabled(session, 1, plugin.id, False)

    (event,) = await audit_events()
    assert (event.category, event.action) == ("user_plugin", "enabled_changed")
    assert event.target_id == str(user_plugin.id)
    assert event.old_values == {"plugin": "audited_plugin", "enabled": True}
    assert event.new_values == {"plugin": "audited_plugin", "enabled": False}
