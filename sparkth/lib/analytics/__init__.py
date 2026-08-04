"""Public API for the analytics emission gateway.

All application code and plugins import analytics functionality from here rather
than reaching into ``sparkth.core.analytics.*`` directly. Implementation lives in
``sparkth/core/analytics/``.

Plugins:
  - subclass ``AnalyticsEventSchema`` to define an event payload schema (declaring
    ``event_type``/``version``),
  - register it from their ``__init__`` via ``register_event_schema(self, MyEvent)``,
  - emit it through ``emit_event`` (reach for the lower-level
    ``ingest_event`` only when the caller already holds an analytics session).
"""

from typing import Any

from sparkth.core.analytics import ANALYTICS_EVENTS, get_event_schema
from sparkth.core.analytics.exceptions import (
    ContinuousAggregateNotFound,
    DuplicateEventTypeError,
    EventNamespaceError,
    UnknownEventTypeError,
)
from sparkth.core.analytics.gateway import ingest_event
from sparkth.core.analytics.maintenance import backfill_continuous_aggregates
from sparkth.core.analytics.reads import LoginActivityPoint, get_login_activity
from sparkth.core.analytics.schemas.base import AnalyticsEventSchema
from sparkth.lib.db import analytics_session_scope
from sparkth.lib.log import get_logger
from sparkth.lib.plugins import SparkthPlugin

logger = get_logger(__name__)

__all__ = [
    "AnalyticsEventSchema",
    "ContinuousAggregateNotFound",
    "DuplicateEventTypeError",
    "EventNamespaceError",
    "UnknownEventTypeError",
    "backfill_continuous_aggregates",
    "emit_event",
    "get_event_schema",
    "LoginActivityPoint",
    "get_login_activity",
    "ingest_event",
    "register_event_schema",
]


async def emit_event(
    event_type: str,
    version: int,
    payload: dict[str, Any],
    actor_id: str | None = None,
) -> None:
    """Validate and land an analytics event, propagating any failure.

    The producer-facing counterpart to :func:`ingest_event`: it opens its own
    analytics session, so callers need no session plumbing. That is the *only*
    thing it adds. It catches nothing — ``UnknownEventTypeError``,
    ``ValidationError``, ``SQLAlchemyError`` and anything else reach the caller
    unchanged, so a broken analytics write is never silently hidden.

    Producers call this from FastAPI background tasks and detached asyncio tasks,
    which run after the response has been sent; a failure there surfaces as an
    unhandled task error in the logs rather than affecting the request that was
    being measured.

    Prefer ``ingest_event`` where the caller already holds an analytics session.

    Args:
        event_type: The registered event name, e.g. ``"chat.message_sent"``.
        version: The schema version, e.g. ``1``.
        payload: The event body, validated against the registered schema.
        actor_id: The acting user's id as a string, stored for provenance.

    Raises:
        UnknownEventTypeError: No schema is registered for this type and version.
        ValidationError: The payload does not match the registered schema.
        SQLAlchemyError: The analytics database could not be reached or written.
    """
    async with analytics_session_scope() as session:
        await ingest_event(session, event_type, version, payload, actor_id=actor_id)


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
