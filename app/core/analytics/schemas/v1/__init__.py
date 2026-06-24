"""Version 1 analytics event schemas.

Re-exports the v1 event models so callers can import them from the package
directly (``from app.analytics.schemas.v1 import UserLoggedIn``) instead of
reaching into each per-event module.
"""

from app.core.analytics.schemas.v1.assessment_submitted import AssessmentSubmitted
from app.core.analytics.schemas.v1.user_logged_in import UserLoggedIn

__all__ = ["AssessmentSubmitted", "UserLoggedIn"]
