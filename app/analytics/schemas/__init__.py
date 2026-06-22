"""Analytics event schemas, registered on import.

Importing this package populates :data:`app.analytics.registry.event_registry`
with every known event schema. Modules that need a populated registry (the
gateway) import this package for its registration side effect.
"""

from app.analytics.registry import event_registry
from app.analytics.schemas.v1.assessment_submitted import AssessmentSubmitted
from app.analytics.schemas.v1.user_logged_in import UserLoggedIn

event_registry.register("assessment.submitted", 1, AssessmentSubmitted)
event_registry.register("user.logged_in", 1, UserLoggedIn)

__all__ = ["AssessmentSubmitted", "UserLoggedIn"]
