"""Core analytics event schemas shipped with Sparkth core.

Import from this package to access the event schema classes directly.
These core schemas are registered into the ``ANALYTICS_EVENTS`` hook
(:mod:`sparkth.core.analytics`) at import time; plugins register their own via
``register_event_schema`` (:mod:`sparkth.lib.analytics`).
"""

from sparkth.core.analytics.schemas.base import AnalyticsEventSchema
from sparkth.core.analytics.schemas.v1 import AssessmentSubmitted, UserLoggedIn

__all__ = ["AnalyticsEventSchema", "AssessmentSubmitted", "UserLoggedIn"]
