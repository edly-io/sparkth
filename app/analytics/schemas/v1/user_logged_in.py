"""Analytics event schema: ``user.logged_in`` (v1).

Emitted fire-and-forget by the login endpoint on a successful password login —
the first real producer wired to the emission gateway.
"""

from app.analytics.schemas.base import AnalyticsEventSchema


class UserLoggedIn(AnalyticsEventSchema):
    username: str
