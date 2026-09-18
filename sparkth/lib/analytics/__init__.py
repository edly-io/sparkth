"""Public API for the analytics emission gateway.

All application code and plugins import analytics functionality from here rather
than reaching into ``sparkth.core.analytics.*`` directly. Implementation lives in
``sparkth/core/analytics/``.

Plugins:
  - subclass ``AnalyticsEventSchema`` to define an event payload schema (declaring
    ``event_type``/``version``),
  - register it from their ``__init__`` via ``register_event_schema(self, MyEvent)``,
  - emit it through ``emit_event``, or ``emit_events`` for a group of related
    events that should share one session (reach for the lower-level
    ``ingest_event`` only when the caller already holds an analytics session).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
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
    "emit_events",
    "PendingEvent",
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
    occurred_at: datetime | None = None,
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
        occurred_at: When the event happened — producers emit from background
            tasks that run after the response, so a turn's events would otherwise
            all be stamped at the end of it and lose their order. Pass the
            moment the thing being recorded actually happened. Defaults to now,
            which is only right for an event emitted where it happened.

    Raises:
        UnknownEventTypeError: No schema is registered for this type and version.
        ValidationError: The payload does not match the registered schema.
        SQLAlchemyError: The analytics database could not be reached or written.
    """
    async with analytics_session_scope() as session:
        await ingest_event(session, event_type, version, payload, actor_id=actor_id, occurred_at=occurred_at)


@dataclass(frozen=True)
class PendingEvent:
    """One event waiting to be landed, for :func:`emit_events`.

    The same values :func:`emit_event` takes, bundled so a caller can hand over a group
    at once. ``occurred_at`` is per-event rather than per-group: events landed together
    did not necessarily happen together.
    """

    event_type: str
    version: int
    payload: dict[str, Any]
    actor_id: str | None = None
    occurred_at: datetime | None = None


async def emit_events(events: Sequence[PendingEvent]) -> None:
    """Land a group of related events, sharing one analytics session.

    :func:`emit_event` opens a session per call, so a producer with a variable number
    of related events — a completion and one event per tool it executed, say — pays
    one session acquisition per event, and, because emitting them in sequence stops
    at the first failure, loses every event behind a failed one.

    This acquires the session once and lands the whole group in one transaction,
    committed once at the end. Ordering is preserved, and an empty sequence is a
    no-op.

    The group is therefore all-or-nothing: a failure on any event — an unregistered
    type, an invalid payload, a database error — leaves none of them landed, so a
    completion never appears without the tool events that belong to it.

    Catches nothing, exactly like :func:`emit_event`: the failure propagates to the
    caller.

    Args:
        events: The events to land, in the order they should appear.

    Raises:
        UnknownEventTypeError: No schema is registered for one of the events.
        ValidationError: One payload does not match its registered schema.
        SQLAlchemyError: The analytics database could not be reached or written.
    """
    if not events:
        return
    async with analytics_session_scope() as session:
        for event in events:
            await ingest_event(
                session,
                event.event_type,
                event.version,
                event.payload,
                actor_id=event.actor_id,
                occurred_at=event.occurred_at,
                commit=False,
            )
        await session.commit()


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
    - **Collision.** A *different* class claiming an already-registered
      ``(event_type, version)`` raises ``DuplicateEventTypeError``. Re-registering the
      identical class is a no-op, so constructing a plugin more than once — a module
      re-import, or a test building its own instance — is not a collision. This follows
      ``KeyedClassHook``'s rule for class registries; only a different class can squat a
      name, which is what the guard is for.
    """
    if not schema.event_type.startswith(f"{plugin.name}."):
        logger.error(
            "Plugin '%s' analytics event '%s' is not namespaced under the plugin name",
            plugin.name,
            schema.event_type,
        )
        raise EventNamespaceError(plugin.name, schema.event_type)

    registered = ANALYTICS_EVENTS.get((schema.event_type, schema.version))
    if registered is schema:
        return
    if registered is not None:
        logger.error(
            "Plugin '%s' analytics event '%s' v%s collides with an already-registered schema",
            plugin.name,
            schema.event_type,
            schema.version,
        )
        raise DuplicateEventTypeError(schema.event_type, schema.version)
    ANALYTICS_EVENTS.add_item(schema)
    logger.info(
        "Registered analytics event '%s' v%s from plugin '%s'",
        schema.event_type,
        schema.version,
        plugin.name,
    )
