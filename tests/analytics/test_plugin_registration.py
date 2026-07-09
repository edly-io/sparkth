"""Tests for plugin-contributed analytics event schemas.

Exercises register_event_schema — the import-time factory a plugin calls from
its __init__ — mirroring how the permissions tests call Permission.create() /
PermissionScope.create() directly.
"""

from collections.abc import Generator

import pytest
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.analytics import ANALYTICS_EVENTS
from sparkth.core.analytics.models import raw_events
from sparkth.lib.analytics import (
    AnalyticsEventSchema,
    DuplicateEventTypeError,
    EventNamespaceError,
    UnknownEventTypeError,
    get_event_schema,
    ingest_event,
    register_event_schema,
)
from sparkth.lib.plugins import SparkthPlugin

# Single source of truth for the fake plugin's identity, so the cleanup fixture's
# key can never desync from the event the tests register.
PLUGIN_NAME = "fake-analytics-plugin"
EVENT_TYPE = f"{PLUGIN_NAME}.thing_happened"
EVENT_VERSION = 1


class _PluginEvent(AnalyticsEventSchema):
    event_type = EVENT_TYPE
    version = EVENT_VERSION

    detail: str


class _ConflictingPluginEvent(AnalyticsEventSchema):
    # Same (event_type, version) as _PluginEvent but a different class.
    event_type = EVENT_TYPE
    version = EVENT_VERSION

    other: str


class _Squatter(AnalyticsEventSchema):
    # event_type is NOT namespaced under the contributing plugin's name — it tries
    # to squat the core "user.logged_in" name (different version, so any failure is
    # the namespace check, not a duplicate).
    event_type = "user.logged_in"
    version = 99

    detail: str


@pytest.fixture(autouse=True)
def _cleanup_plugin_registrations() -> Generator[None, None, None]:
    """Remove the plugin event key from the hook after each test.

    register_event_schema writes straight into the process-wide ANALYTICS_EVENTS
    hook; without this a later test registering a different class under the same key
    would hit a spurious DuplicateEventTypeError from leftover state.
    """
    yield
    ANALYTICS_EVENTS.remove((EVENT_TYPE, EVENT_VERSION))


def test_register_event_schema_adds_to_hook() -> None:
    plugin = SparkthPlugin(PLUGIN_NAME)
    register_event_schema(plugin, _PluginEvent)

    assert get_event_schema(EVENT_TYPE, EVENT_VERSION) is _PluginEvent


def test_register_event_schema_rejects_re_registration() -> None:
    plugin = SparkthPlugin(PLUGIN_NAME)
    register_event_schema(plugin, _PluginEvent)
    # Re-registering the same schema is startup-fatal
    with pytest.raises(DuplicateEventTypeError):
        register_event_schema(plugin, _PluginEvent)

    assert get_event_schema(EVENT_TYPE, EVENT_VERSION) is _PluginEvent


def test_register_event_schema_rejects_unnamespaced_event() -> None:
    plugin = SparkthPlugin(PLUGIN_NAME)
    # "user.logged_in" is not prefixed with "fake-analytics-plugin.", so registration
    # rejects it before it can squat the core event name.
    with pytest.raises(EventNamespaceError):
        register_event_schema(plugin, _Squatter)


def test_register_event_schema_raises_on_duplicate_schema() -> None:
    plugin = SparkthPlugin(PLUGIN_NAME)
    register_event_schema(plugin, _PluginEvent)
    # A different class claiming the same (event_type, version) is startup-fatal.
    with pytest.raises(DuplicateEventTypeError):
        register_event_schema(plugin, _ConflictingPluginEvent)
    # The first registration is unaffected.
    assert get_event_schema(EVENT_TYPE, EVENT_VERSION) is _PluginEvent


async def test_plugin_event_round_trips_through_gateway(analytics_session: AsyncSession) -> None:
    # The whole point of the feature: a plugin-registered event validates and lands
    # a row through the real gateway.
    plugin = SparkthPlugin(PLUGIN_NAME)
    register_event_schema(plugin, _PluginEvent)

    await ingest_event(
        analytics_session,
        EVENT_TYPE,
        EVENT_VERSION,
        {"detail": "hello"},
        actor_id="7",
    )

    row = (await analytics_session.execute(select(raw_events))).mappings().one()
    assert row["event_type"] == EVENT_TYPE
    assert row["event_version"] == EVENT_VERSION
    assert row["payload"] == {"detail": "hello"}


def test_unregistered_plugin_event_is_unknown() -> None:
    with pytest.raises(UnknownEventTypeError):
        get_event_schema("never.registered", 1)
