"""Public API for the analytics emission gateway.

All application code and plugins import analytics functionality from here rather
than reaching into ``app.core.analytics.*`` directly. Implementation lives in
``app/core/analytics/``.

Plugins:
  - subclass ``AnalyticsEventSchema`` to define an event payload schema (declaring
    ``event_type``/``version`` and, optionally, ``server_only``),
  - register it from their ``__init__`` via ``ANALYTICS_SCHEMAS.add_item(self, MyEvent)``,
  - emit it through ``ingest_event``.
"""

from app.core.analytics.exceptions import (
    DuplicateEventTypeError,
    EventNamespaceError,
    UnknownEventTypeError,
)
from app.core.analytics.gateway import ingest_event
from app.core.analytics.registry import EventRegistry
from app.core.analytics.schemas.base import AnalyticsEventSchema
from app.lib.analytics.hooks import ANALYTICS_SCHEMAS
from app.lib.log import get_logger

logger = get_logger(__name__)

__all__ = [
    "ANALYTICS_SCHEMAS",
    "AnalyticsEventSchema",
    "DuplicateEventTypeError",
    "EventNamespaceError",
    "EventRegistry",
    "UnknownEventTypeError",
    "ingest_event",
    "initialize_event_registry",
]


def initialize_event_registry() -> None:
    """Drain the ``ANALYTICS_SCHEMAS`` hook into the gateway's event registry.

    Plugins contribute schema classes from their ``__init__`` (populating the
    hook); this copies each into the ``EventRegistry`` singleton the gateway
    resolves against. Mirrors ``initialize_permissions_registry`` for the
    permissions vocabulary.

    Three startup-fatal guards (all deliberately stricter than the permissions
    drain, because they protect data integrity):

    - **Identity.** Every plugin schema must declare both ``event_type`` and
      ``version`` as class attributes before any further checks run. A missing
      ClassVar raises ``TypeError`` with the plugin name logged, so the startup
      crash is diagnosable regardless of which attribute is absent.
    - **Namespace.** Every plugin event's ``event_type`` must be prefixed with the
      contributing plugin's name (e.g. plugin ``slack`` → ``"slack.*"``), else
      ``EventNamespaceError``. This stops a plugin squatting a core or another
      plugin's event name and makes a cross-plugin ``DuplicateEventTypeError``
      structurally unreachable.
    - **Collision.** A schema conflicting with an existing ``(event_type,
      version)`` raises ``DuplicateEventTypeError``. The error is re-raised with
      the offending plugin logged first, so a fatal startup is diagnosable.

    Idempotent for the same hook contents: ``EventRegistry.register`` is a no-op
    for an already-registered class, so calling this more than once (e.g. test
    setup and a second ``assemble_app``) is safe.

    Plugins must already be instantiated; ``assemble_app`` registers plugin
    routes before calling this, so the hook is populated.
    """
    registry = EventRegistry()
    for plugin, schema in ANALYTICS_SCHEMAS.iter_items():
        missing = [attr for attr in ("event_type", "version") if not hasattr(schema, attr)]
        if missing:
            exc = TypeError(
                f"{schema.__qualname__} must declare {missing} as class attributes before it can be registered"
            )
            logger.error(
                "Plugin '%s' schema %s is missing required identity ClassVars: %s",
                plugin.name,
                schema.__qualname__,
                exc,
            )
            raise exc
        if not schema.event_type.startswith(f"{plugin.name}."):
            raise EventNamespaceError(plugin.name, schema.event_type)
        try:
            registry.register(schema)
        except DuplicateEventTypeError:
            logger.error(
                "Plugin '%s' analytics event '%s' v%s collides with an already-registered schema",
                plugin.name,
                schema.event_type,
                schema.version,
            )
            raise
        logger.info(
            "  ✓ Registered analytics event '%s' v%s from plugin '%s'",
            schema.event_type,
            schema.version,
            plugin.name,
        )
