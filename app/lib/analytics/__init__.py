"""Public API for the analytics emission gateway.

All application code and plugins import analytics functionality from here rather
than reaching into ``app.core.analytics.*`` directly. Implementation lives in
``app/core/analytics/``.

Plugins:
  - subclass ``AnalyticsEventSchema`` to define an event payload schema (declaring
    ``event_type``/``version``),
  - register it from their ``__init__`` via ``register_analytics_event(self, MyEvent)``,
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
from app.lib.log import get_logger
from app.lib.plugins import SparkthPlugin

logger = get_logger(__name__)

__all__ = [
    "AnalyticsEventSchema",
    "DuplicateEventTypeError",
    "EventNamespaceError",
    "EventRegistry",
    "UnknownEventTypeError",
    "ingest_event",
    "register_analytics_event",
]


def register_analytics_event(plugin: SparkthPlugin, schema: type[AnalyticsEventSchema]) -> None:
    """Register a plugin's event schema on the gateway's ``EventRegistry``.

    Call this from a plugin's ``__init__``. Registration happens at
    import time, straight into the ``EventRegistry`` singleton the gateway resolves
    against.

    Three startup-fatal guards, all enforced here at registration time so a
    misconfigured plugin crashes the process at import rather than at first emit:

    - **Identity.** The schema must declare both ``event_type`` and ``version`` as
      class attributes; a missing ClassVar raises ``TypeError`` (with the plugin
      name logged). Checked before the namespace guard, whose ``event_type`` access
      would otherwise raise a bare ``AttributeError``.
    - **Namespace.** ``event_type`` must be prefixed with the contributing plugin's
      name (e.g. plugin ``slack`` → ``"slack.*"``), else ``EventNamespaceError``.
      This stops a plugin squatting a core or another plugin's event name.
    - **Collision.** A *different* class claiming an already-registered
      ``(event_type, version)`` raises ``DuplicateEventTypeError``.

    Idempotent for the same class: ``EventRegistry.register`` is a no-op when the
    same schema is registered again, so a module re-imported in tests is safe.
    """
    missing = [attr for attr in ("event_type", "version") if not hasattr(schema, attr)]
    if missing:
        exc = TypeError(f"{schema.__qualname__} must declare {missing} as class attributes before it can be registered")
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
        EventRegistry().register(schema)
    except DuplicateEventTypeError:
        logger.error(
            "Plugin '%s' analytics event '%s' v%s collides with an already-registered schema",
            plugin.name,
            schema.event_type,
            schema.version,
        )
        raise
    logger.info(
        "Registered analytics event '%s' v%s from plugin '%s'",
        schema.event_type,
        schema.version,
        plugin.name,
    )
