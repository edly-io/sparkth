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
NEW_SECRET = "n3w-lms-p4ssw0rd"
URL = "https://x"
NEW_URL = "https://y"
PLUGIN_NAME = "audited_plugin"


@pytest.fixture
async def plugin(session: AsyncSession) -> Plugin:
    plugin = Plugin(
        name=PLUGIN_NAME,
        is_core=True,
        enabled=True,
        config_schema={"properties": {"url": {}, "lms_password": {"secret": True}}},
    )
    session.add(plugin)
    await session.flush()
    return plugin


@pytest.fixture
def passthrough_validation() -> Iterator[None]:
    with patch.object(PluginService, "validate_user_config", side_effect=lambda plugin, config: config):
        yield


async def test_create_preference_records_config_keys_only(
    session: AsyncSession, plugin: Plugin, audit_events: AuditEventsFetcher
) -> None:
    assert plugin.id is not None
    preference = await PluginService().create_preference(
        session, 1, plugin.id, {"url": "https://x", "lms_password": SECRET}
    )

    (event,) = await audit_events()
    assert (event.category, event.action) == ("user_plugin", "config_created")
    assert event.outcome == "success"
    assert event.target_type == "user_plugin"
    assert event.target_id == str(preference.id)
    assert event.new_values == {"plugin": PLUGIN_NAME, "keys": ["lms_password", "url"]}
    assert SECRET not in event.canonical_bytes.decode()


async def test_update_preference_config_records_old_and_new_keys(
    session: AsyncSession, plugin: Plugin, audit_events: AuditEventsFetcher, passthrough_validation: None
) -> None:
    assert plugin.id is not None
    service = PluginService()
    await service.create_preference(session, 1, plugin.id, {"url": "https://x"})
    await service.update_preference_config(session, 1, plugin, {"lms_password": SECRET})
    await session.commit()

    _, event = await audit_events()
    assert (event.category, event.action) == ("user_plugin", "config_updated")
    assert event.old_values == {"plugin": PLUGIN_NAME, "keys": ["url"]}
    assert event.new_values == {
        "plugin": PLUGIN_NAME,
        "keys": ["lms_password", "url"],
        "changed": ["lms_password"],
        "secret_changed": True,
    }
    assert SECRET not in event.canonical_bytes.decode()


@pytest.mark.parametrize(
    ("stored", "update", "changed", "secret_changed"),
    [
        pytest.param({"url": URL, "lms_password": SECRET}, {"url": NEW_URL}, ["url"], False, id="plain-field-edit"),
        pytest.param(
            {"url": URL, "lms_password": SECRET},
            {"lms_password": NEW_SECRET},
            ["lms_password"],
            True,
            id="replaced-secret",
        ),
        pytest.param({"url": URL}, {"url": URL}, [], False, id="nothing-changed"),
    ],
)
async def test_update_preference_config_records_changed_fields(
    session: AsyncSession,
    plugin: Plugin,
    audit_events: AuditEventsFetcher,
    passthrough_validation: None,
    stored: dict[str, str],
    update: dict[str, str],
    changed: list[str],
    secret_changed: bool,
) -> None:
    assert plugin.id is not None
    service = PluginService()
    await service.create_preference(session, 1, plugin.id, stored)
    await service.update_preference_config(session, 1, plugin, update)
    await session.commit()

    _, event = await audit_events()
    keys = sorted({**stored, **update})
    assert event.old_values == {"plugin": PLUGIN_NAME, "keys": sorted(stored)}
    assert event.new_values == {
        "plugin": PLUGIN_NAME,
        "keys": keys,
        "changed": changed,
        "secret_changed": secret_changed,
    }
    sealed = event.canonical_bytes.decode()
    for value in (SECRET, NEW_SECRET, NEW_URL):
        assert value not in sealed


async def test_update_preference_config_without_secret_fields_flags_no_secret(
    session: AsyncSession, audit_events: AuditEventsFetcher, passthrough_validation: None
) -> None:
    plugin = Plugin(name=PLUGIN_NAME, is_core=True, enabled=True, config_schema={})
    session.add(plugin)
    await session.flush()
    assert plugin.id is not None
    service = PluginService()
    await service.create_preference(session, 1, plugin.id, {"url": URL})
    await service.update_preference_config(session, 1, plugin, {"url": NEW_URL})
    await session.commit()

    _, event = await audit_events()
    assert event.old_values == {"plugin": PLUGIN_NAME, "keys": ["url"]}
    assert event.new_values == {"plugin": PLUGIN_NAME, "keys": ["url"], "changed": ["url"], "secret_changed": False}
    assert NEW_URL not in event.canonical_bytes.decode()


async def test_update_enabled_records_transition(
    session: AsyncSession, plugin: Plugin, audit_events: AuditEventsFetcher
) -> None:
    assert plugin.id is not None
    preference = await PluginService().update_preference_enabled(session, 1, plugin.id, False)

    (event,) = await audit_events()
    assert (event.category, event.action) == ("user_plugin", "enabled_changed")
    assert event.target_id == str(preference.id)
    assert event.old_values == {"plugin": PLUGIN_NAME, "enabled": True}
    assert event.new_values == {"plugin": PLUGIN_NAME, "enabled": False}
