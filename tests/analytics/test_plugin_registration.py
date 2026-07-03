"""Tests for plugin-contributed analytics event schemas.

Exercises register_analytics_event — the import-time factory a plugin calls from
its __init__ — mirroring how the permissions tests call Permission.create() /
PermissionScope.create() directly.
"""

from collections.abc import Generator

import pytest
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.analytics.models import raw_events
from app.lib.analytics import (
    AnalyticsEventSchema,
    DuplicateEventTypeError,
    EventNamespaceError,
    EventRegistry,
    UnknownEventTypeError,
    ingest_event,
    register_analytics_event,
)
from app.lib.plugins import SparkthPlugin


class _PluginEvent(AnalyticsEventSchema):
    event_type = "fake-analytics-plugin.thing_happened"
    version = 1

    detail: str


class _ConflictingPluginEvent(AnalyticsEventSchema):
    # Same (event_type, version) as _PluginEvent but a different class.
    event_type = "fake-analytics-plugin.thing_happened"
    version = 1

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
    """Remove the plugin event key from the singleton after each test.

    register_analytics_event writes straight into the process-wide EventRegistry;
    without this a later test registering a different class under the same key would
    hit a spurious DuplicateEventTypeError from leftover state.
    """
    yield
    EventRegistry()._schemas.pop(("fake-analytics-plugin.thing_happened", 1), None)


def test_register_analytics_event_adds_to_registry() -> None:
    plugin = SparkthPlugin("fake-analytics-plugin")
    register_analytics_event(plugin, _PluginEvent)

    assert EventRegistry().resolve("fake-analytics-plugin.thing_happened", 1) is _PluginEvent


def test_register_analytics_event_is_idempotent() -> None:
    plugin = SparkthPlugin("fake-analytics-plugin")
    register_analytics_event(plugin, _PluginEvent)
    register_analytics_event(plugin, _PluginEvent)  # same class is a no-op

    assert EventRegistry().resolve("fake-analytics-plugin.thing_happened", 1) is _PluginEvent


def test_register_analytics_event_rejects_unnamespaced_event() -> None:
    plugin = SparkthPlugin("fake-analytics-plugin")
    # "user.logged_in" is not prefixed with "fake-analytics-plugin.", so registration
    # rejects it before it can squat the core event name.
    with pytest.raises(EventNamespaceError):
        register_analytics_event(plugin, _Squatter)


def test_register_analytics_event_raises_on_duplicate_schema() -> None:
    plugin = SparkthPlugin("fake-analytics-plugin")
    register_analytics_event(plugin, _PluginEvent)
    # A different class claiming the same (event_type, version) is startup-fatal.
    with pytest.raises(DuplicateEventTypeError):
        register_analytics_event(plugin, _ConflictingPluginEvent)
    # The first registration is unaffected.
    assert EventRegistry().resolve("fake-analytics-plugin.thing_happened", 1) is _PluginEvent


def test_register_analytics_event_raises_on_missing_classvars() -> None:
    class _IncompleteEvent(AnalyticsEventSchema):
        detail: str  # forgot event_type and version

    plugin = SparkthPlugin("fake-analytics-plugin")
    with pytest.raises(TypeError, match="_IncompleteEvent"):
        register_analytics_event(plugin, _IncompleteEvent)


async def test_plugin_event_round_trips_through_gateway(analytics_session: AsyncSession) -> None:
    # The whole point of the feature: a plugin-registered event validates and lands
    # a row through the real gateway.
    plugin = SparkthPlugin("fake-analytics-plugin")
    register_analytics_event(plugin, _PluginEvent)

    await ingest_event(
        analytics_session,
        "fake-analytics-plugin.thing_happened",
        1,
        {"detail": "hello"},
        actor_id="7",
    )

    row = (await analytics_session.execute(select(raw_events))).mappings().one()
    assert row["event_type"] == "fake-analytics-plugin.thing_happened"
    assert row["event_version"] == 1
    assert row["payload"] == {"detail": "hello"}


def test_unregistered_plugin_event_is_unknown() -> None:
    with pytest.raises(UnknownEventTypeError):
        EventRegistry().resolve("never.registered", 1)
