"""Analytics event schema: ``user.logged_in`` (v1).

Emitted from a background task by both login routes: password login and the Google
callback. The user is identified by the row's ``actor_id``.

Rows written before ``method`` existed carried the username instead; analytics migration
``6ccbebfb6a25`` replaced it with ``method: password``, the only route that emitted then.
"""

from enum import StrEnum

from sparkth.core.analytics.schemas.base import AnalyticsEventSchema


class LoginMethod(StrEnum):
    """How a user logged in.

    A new login route adds its member here and emits ``user.logged_in`` with it. Adding a
    member keeps v1; renaming or removing one breaks saved queries and needs a new version.
    """

    PASSWORD = "password"
    GOOGLE = "google"


class UserLoggedIn(AnalyticsEventSchema):
    """A user logged in."""

    event_type = "user.logged_in"
    version = 1

    method: LoginMethod
