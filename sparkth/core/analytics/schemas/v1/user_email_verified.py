"""Analytics event schema: ``user.email_verified`` (v1).

Emitted from a background task when a user redeems a verification token. The user is
identified by the row's ``actor_id`` and ``occurred_at`` is the user's ``email_verified_at``.
"""

from sparkth.core.analytics.schemas.base import AnalyticsEventSchema


class UserEmailVerified(AnalyticsEventSchema):
    """A user verified their email address."""

    event_type = "user.email_verified"
    version = 1
