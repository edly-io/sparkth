"""Core analytics event schemas shipped with Sparkth core.

Import from this package to access the event schema classes directly.
Registration of these schemas into :class:`~app.core.analytics.registry.EventRegistry`
happens automatically on first ``EventRegistry()`` construction, which
``assemble_app`` triggers at startup.
"""

from app.core.analytics.schemas.base import AnalyticsEventSchema
from app.core.analytics.schemas.v1 import AssessmentSubmitted, UserLoggedIn

__all__ = ["AnalyticsEventSchema", "AssessmentSubmitted", "UserLoggedIn"]
