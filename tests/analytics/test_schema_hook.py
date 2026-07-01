"""Tests for plugin-contributed analytics event schemas.

Exercises the ANALYTICS_SCHEMAS hook and the initialize_event_registry() drain,
mirroring how the permissions tests call the registry initializers directly (the
FastAPI lifespan does not run under the test client).
"""

from collections.abc import Generator

import pytest
from sqlalchemy import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.analytics.models import raw_events
from app.lib.analytics import (
    ANALYTICS_SCHEMAS,
    AnalyticsEventSchema,
    DuplicateEventTypeError,
    EventNamespaceError,
    EventRegistry,
    UnknownEventTypeError,
    ingest_event,
    initialize_event_registry,
)
from app.lib.plugins import SparkthPlugin


class _PluginEvent(AnalyticsEventSchema):
    event_type = "fake-analytics-plugin.thing_happened"
    version = 1
    server_only = False  # explicit opt-in to client emission (default is server-only)

    detail: str


class _ConflictingPluginEvent(AnalyticsEventSchema):
    # Same (event_type, version) as _PluginEvent but a different class — triggers
    # DuplicateEventTypeError when both are drained for the same plugin.
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
    """Remove plugin event keys from the singleton after each test.

    Mirrors the conftest cleanup for test.client_event — without this, a later
    test registering a different class under the same key would hit a spurious
    DuplicateEventTypeError from leftover state.
    """
    yield
    EventRegistry()._schemas.pop(("fake-analytics-plugin.thing_happened", 1), None)
    EventRegistry()._server_only.pop(("fake-analytics-plugin.thing_happened", 1), None)


def test_initialize_event_registry_drains_hook_into_registry() -> None:
    plugin = SparkthPlugin("fake-analytics-plugin")
    ANALYTICS_SCHEMAS.add_item(plugin, _PluginEvent)

    initialize_event_registry()

    assert EventRegistry().resolve("fake-analytics-plugin.thing_happened", 1) is _PluginEvent
    # _PluginEvent opted into client emission with server_only = False.
    assert EventRegistry().is_server_only("fake-analytics-plugin.thing_happened", 1) is False
    # Keep `plugin` referenced until after the assertion — the hook holds plugins
    # in a WeakKeyDictionary, so a garbage-collected plugin drops out.
    assert plugin.name == "fake-analytics-plugin"


def test_initialize_event_registry_is_idempotent() -> None:
    plugin = SparkthPlugin("fake-analytics-plugin")
    ANALYTICS_SCHEMAS.add_item(plugin, _PluginEvent)

    initialize_event_registry()
    initialize_event_registry()  # second drain must not raise (same class is a no-op)

    assert EventRegistry().resolve("fake-analytics-plugin.thing_happened", 1) is _PluginEvent
    assert plugin.name == "fake-analytics-plugin"


def test_initialize_event_registry_rejects_unnamespaced_event() -> None:
    plugin = SparkthPlugin("fake-analytics-plugin")
    ANALYTICS_SCHEMAS.add_item(plugin, _Squatter)

    # "user.logged_in" is not prefixed with "fake-analytics-plugin.", so the drain
    # rejects it before it can squat the core event name.
    with pytest.raises(EventNamespaceError):
        initialize_event_registry()
    assert plugin.name == "fake-analytics-plugin"


async def test_plugin_event_round_trips_through_gateway(analytics_session: AsyncSession) -> None:
    # The whole point of the feature: a plugin-registered event validates and lands
    # a row through the real gateway.
    plugin = SparkthPlugin("fake-analytics-plugin")
    ANALYTICS_SCHEMAS.add_item(plugin, _PluginEvent)
    initialize_event_registry()

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
    assert plugin.name == "fake-analytics-plugin"


def test_initialize_event_registry_raises_on_duplicate_schema() -> None:
    plugin = SparkthPlugin("fake-analytics-plugin")
    ANALYTICS_SCHEMAS.add_item(plugin, _PluginEvent)
    ANALYTICS_SCHEMAS.add_item(plugin, _ConflictingPluginEvent)

    # First schema registers fine; second claims the same (event_type, version)
    # with a different class, which is startup-fatal.
    with pytest.raises(DuplicateEventTypeError):
        initialize_event_registry()
    # The first registration is unaffected.
    assert EventRegistry().resolve("fake-analytics-plugin.thing_happened", 1) is _PluginEvent
    assert plugin.name == "fake-analytics-plugin"


def test_initialize_event_registry_raises_on_missing_classvars() -> None:
    class _IncompleteEvent(AnalyticsEventSchema):
        detail: str  # forgot event_type and version

    plugin = SparkthPlugin("fake-analytics-plugin")
    ANALYTICS_SCHEMAS.add_item(plugin, _IncompleteEvent)

    with pytest.raises(TypeError, match="_IncompleteEvent"):
        initialize_event_registry()
    assert plugin.name == "fake-analytics-plugin"


def test_unregistered_plugin_event_is_unknown() -> None:
    with pytest.raises(UnknownEventTypeError):
        EventRegistry().resolve("never.registered", 1)
