"""Analytics event schema: ``user.registered`` (v1).

Emitted from a background task when an account is created: password registration and a
first Google sign-in. Linking Google to an existing account emits nothing. The user is
identified by the row's ``actor_id`` and ``occurred_at`` is the account's ``created_at``.
"""

from sparkth.core.analytics.schemas.base import AnalyticsEventSchema
from sparkth.core.analytics.schemas.v1.user_logged_in import LoginMethod


class UserRegistered(AnalyticsEventSchema):
    """A user account was created."""

    event_type = "user.registered"
    version = 1

    method: LoginMethod
