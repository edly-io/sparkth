"""Version 1 analytics event schemas.

Re-exports the v1 event models so callers can import them from the package
directly (``from sparkth.core.analytics.schemas.v1 import AssessmentSubmitted``) instead of
reaching into each per-event module.
"""

from sparkth.core.analytics.schemas.v1.assessment_submitted import AssessmentSubmitted
from sparkth.core.analytics.schemas.v1.user_email_verified import UserEmailVerified
from sparkth.core.analytics.schemas.v1.user_logged_in import LoginMethod, UserLoggedIn
from sparkth.core.analytics.schemas.v1.user_registered import UserRegistered

__all__ = ["AssessmentSubmitted", "LoginMethod", "UserEmailVerified", "UserLoggedIn", "UserRegistered"]
