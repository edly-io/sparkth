"""Analytics event schema: ``user.logged_in`` (v1).

Emitted fire-and-forget by the login endpoint on a successful password login —
the first real producer wired to the emission gateway, via ``ingest_event``.
"""

from sparkth.core.analytics.schemas import AnalyticsEventSchema


class UserLoggedIn(AnalyticsEventSchema):
    event_type = "user.logged_in"
    version = 1

    username: str
