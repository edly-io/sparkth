"""Public API for the analytics emission gateway.

All application code and plugins import analytics functionality from here rather
than reaching into ``app.analytics.*`` directly. Implementation lives in
``app/analytics/``.
"""

from app.analytics.exceptions import UnknownEventTypeError
from app.analytics.gateway import ingest_event

__all__ = [
    "UnknownEventTypeError",
    "ingest_event",
]
