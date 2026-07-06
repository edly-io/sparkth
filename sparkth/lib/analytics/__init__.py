"""Public API for the analytics emission gateway.

All application code and plugins import analytics functionality from here rather
than reaching into ``sparkth.core.analytics.*`` directly. Implementation lives in
``sparkth/core/analytics/``.

Plugins:
  - subclass ``AnalyticsEventSchema`` to define an event payload schema (declaring
    ``event_type``/``version``),
  - register it from their ``__init__`` via ``register_event_schema(self, MyEvent)``,
  - emit it through ``ingest_event``.
"""

from sparkth.core.analytics import ANALYTICS_EVENTS, get_event_schema
from sparkth.core.analytics.exceptions import (
    DuplicateEventTypeError,
    EventNamespaceError,
    UnknownEventTypeError,
)
from sparkth.core.analytics.gateway import ingest_event
from sparkth.core.analytics.schemas.base import AnalyticsEventSchema
from sparkth.lib.log import get_logger
from sparkth.lib.plugins import SparkthPlugin

logger = get_logger(__name__)

__all__ = [
    "AnalyticsEventSchema",
    "DuplicateEventTypeError",
    "EventNamespaceError",
    "UnknownEventTypeError",
    "get_event_schema",
    "ingest_event",
    "register_event_schema",
]


def register_event_schema(plugin: SparkthPlugin, schema: type[AnalyticsEventSchema]) -> None:
    """Register a plugin's event schema on the ``ANALYTICS_EVENTS`` hook.

    Call this from a plugin's ``__init__``. Registration happens at
    import time, straight into the ``ANALYTICS_EVENTS`` hook the gateway resolves
    against.

    Two startup-fatal guards, enforced here so a misconfigured plugin crashes the
    process at import rather than at first emit (a third — that the schema declares
    ``event_type``/``version`` — is enforced on ``AnalyticsEventSchema`` itself, at
    class-definition time, via ``__init_subclass__``):

    - **Namespace.** ``event_type`` must be prefixed with the contributing plugin's
      name (e.g. plugin ``slack`` → ``"slack.*"``), else ``EventNamespaceError``.
      This stops a plugin squatting a core or another plugin's event name.
    - **Collision.** Any class claiming an already-registered ``(event_type, version)``
      raises ``DuplicateEventTypeError``.
    """
    if not schema.event_type.startswith(f"{plugin.name}."):
        logger.error(
            "Plugin '%s' analytics event '%s' is not namespaced under the plugin name",
            plugin.name,
            schema.event_type,
        )
        raise EventNamespaceError(plugin.name, schema.event_type)
    try:
        ANALYTICS_EVENTS.add_item(schema)
    except ValueError as exc:
        logger.error(
            "Plugin '%s' analytics event '%s' v%s collides with an already-registered schema",
            plugin.name,
            schema.event_type,
            schema.version,
        )
        raise DuplicateEventTypeError(schema.event_type, schema.version) from exc
    logger.info(
        "Registered analytics event '%s' v%s from plugin '%s'",
        schema.event_type,
        schema.version,
        plugin.name,
    )
