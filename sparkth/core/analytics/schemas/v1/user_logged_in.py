"""Analytics event schema: ``user.logged_in`` (v1).

Emitted from a background task by the login endpoint on a successful password
login — the first real producer wired to the emission gateway, via ``emit_event``.
"""

from sparkth.core.analytics.schemas import AnalyticsEventSchema


class UserLoggedIn(AnalyticsEventSchema):
    event_type = "user.logged_in"
    version = 1

    username: str
