"""An XBlock that holds a reference to a Sparkth-hosted PXC activity and renders it.

The block itself stores no activity data: only the activity type's name and the placement id
Sparkth minted at publish time. Before rendering it mints a short-lived token carrying the
Open edX user id, course id and placement, signed with the secret shared with Sparkth, and
renders an iframe at Sparkth carrying that token. The secret stays server-side at both ends
and only the token travels through the browser.
"""

from typing import Any

from django.conf import settings
from web_fragments.fragment import Fragment
from xblock.core import XBlock
from xblock.fields import Scope, String

from sparkth_pxc.tokens import mint_launch_token


def build_embed_iframe(
    base_url: str,
    activity: str,
    placement: str,
    course_id: str,
    user_id: str,
    secret: str,
    ttl: int,
) -> str:
    """The sandboxed iframe that loads one activity for one learner from Sparkth.

    A module-level function rather than a method so it is testable without an XBlock runtime.
    """
    token = mint_launch_token(activity, placement, course_id, user_id, secret, ttl)
    base = base_url.rstrip("/")
    # allow-same-origin is required: the embedded page fetches its own config from Sparkth, and
    # without it the frame gets an opaque origin, making that fetch cross-origin and blocked.
    return (
        f'<iframe src="{base}/api/v1/pxc/embed?token={token}"'
        ' style="width:100%;border:none;display:block;min-height:24em"'
        ' sandbox="allow-scripts allow-forms allow-same-origin"></iframe>'
    )


class SparkthPxcXBlock(XBlock):  # type: ignore[misc]
    """A PXC activity hosted by Sparkth. Holds a reference to it, never its data."""

    display_name = String(display_name="Display Name", default="PXC Activity", scope=Scope.settings)
    activity = String(
        display_name="Activity",
        default="",
        scope=Scope.settings,
        help="The Sparkth-hosted activity type's name, set when the course was published.",
    )
    placement = String(
        display_name="Placement",
        default="",
        scope=Scope.settings,
        help="The placement id Sparkth minted for this block, set when the course was published.",
    )

    def student_view(self, context: dict[str, Any] | None = None) -> Fragment:
        """Render the iframe that loads the activity from Sparkth."""
        return Fragment(
            build_embed_iframe(
                str(settings.SPARKTH_PXC_BASE_URL),
                str(self.activity),
                str(self.placement),
                self._course_id(),
                str(self.scope_ids.user_id),
                settings.SPARKTH_PXC_LAUNCH_SECRET,
                settings.SPARKTH_PXC_LAUNCH_TOKEN_TTL_SECONDS,
            )
        )

    def _course_id(self) -> str:
        """The course this block sits in, from its usage id's course key."""
        course_key = getattr(self.scope_ids.usage_id, "course_key", None)
        return str(course_key) if course_key else ""
