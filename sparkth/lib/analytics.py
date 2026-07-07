"""Public API for the analytics emission gateway.

All application code and plugins import analytics functionality from here rather
than reaching into ``sparkth.core.analytics.*`` directly. Implementation lives in
``app/core/analytics/``.
"""

from sparkth.core.analytics.exceptions import DuplicateEventTypeError, UnknownEventTypeError
from sparkth.core.analytics.gateway import ingest_event
from sparkth.core.analytics.schemas.base import AnalyticsEventSchema

__all__ = [
    "AnalyticsEventSchema",
    "DuplicateEventTypeError",
    "UnknownEventTypeError",
    "ingest_event",
]
