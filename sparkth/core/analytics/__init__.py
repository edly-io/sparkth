"""Analytics subsystem: the emission gateway write path and event vocabulary.

Holds the versioned event schema hook (``ANALYTICS_EVENTS``), the event schemas,
and the gateway that validates and lands events into the analytics database.
Producers emit through ``ingest_event``.

``ANALYTICS_EVENTS`` is a :class:`~sparkth.lib.hooks.KeyedItemHook` mapping
``(event_type, version)`` to the ``AnalyticsEventSchema`` subclass that validates
that event's payload — the single source of truth the gateway resolves against.
Core events are seeded at import (bottom of this module); plugins register their own
from ``__init__`` via ``register_event_schema`` (``sparkth/lib/analytics``), which
validates the plugin-name namespace and collision before calling
``ANALYTICS_EVENTS.add_item``.
"""

from sparkth.core.analytics.exceptions import UnknownEventTypeError
from sparkth.core.analytics.schemas.base import AnalyticsEventSchema
from sparkth.core.analytics.schemas.v1 import AssessmentSubmitted, UserLoggedIn
from sparkth.lib.hooks import KeyedItemHook

# Every event the platform knows. Core events are seeded just below; plugins add
# their own via register_event_schema(). This hook is the single source of truth —
# get_event_schema() resolves names against it.
ANALYTICS_EVENTS: KeyedItemHook[tuple[str, int], type[AnalyticsEventSchema]] = KeyedItemHook(
    key=lambda schema: (schema.event_type, schema.version)
)
ANALYTICS_EVENTS.add_item(AssessmentSubmitted)
ANALYTICS_EVENTS.add_item(UserLoggedIn)


def get_event_schema(event_type: str, version: int) -> type[AnalyticsEventSchema]:
    """Return the schema for ``(event_type, version)``, or raise UnknownEventTypeError."""
    schema = ANALYTICS_EVENTS.get((event_type, version))
    if schema is None:
        raise UnknownEventTypeError(event_type, version)
    return schema
