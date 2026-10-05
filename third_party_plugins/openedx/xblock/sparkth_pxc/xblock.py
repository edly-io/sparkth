"""An XBlock that holds a reference to a Sparkth-hosted PXC activity and renders it.

The block itself stores no activity data: only the activity type's name and the placement id
Sparkth minted at publish time. Before rendering it mints a short-lived token carrying the
Open edX user id, course id and placement, signed with the secret shared with Sparkth, and
renders an iframe at Sparkth carrying that token. The secret stays server-side at both ends
and only the token travels through the browser.
"""

from typing import Any
from uuid import uuid4

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
    permission: str,
    secret: str,
    ttl: int,
) -> str:
    """The sandboxed iframe that loads one activity for one learner from Sparkth.

    A module-level function rather than a method so it is testable without an XBlock runtime.
    """
    token = mint_launch_token(activity, placement, course_id, user_id, permission, secret, ttl)
    base = base_url.rstrip("/")
    # No allow-same-origin: the frame keeps an opaque origin, so activity code in it cannot reach
    # the storage of the origin that serves it.
    return (
        f'<iframe src="{base}/api/v1/pxc/embed?token={token}"'
        ' style="width:100%;border:none;display:block;min-height:24em"'
        ' sandbox="allow-scripts allow-forms"></iframe>'
    )


# Inline rather than a stylesheet: this package ships no static assets, so an Open edX image
# can install it without re-running the asset pipeline.
_EDITOR_NOTICE = (
    '<p style="margin:0 0 1em;padding:0.75em 1em;border-left:3px solid #0075b4;'
    'background:#f2f8fb;font-size:0.9em;line-height:1.5">'
    "This activity's content is stored in Sparkth, not in Studio. Click <strong>Save</strong> "
    "inside the activity to keep your changes &mdash; Studio's Save and Cancel buttons do not "
    "apply to them."
    "</p>"
)


def build_editor_html(
    base_url: str,
    activity: str,
    placement: str,
    course_id: str,
    user_id: str,
    secret: str,
    ttl: int,
) -> str:
    """The editing view's markup: the notice, then the activity in edit mode.

    Takes no permission argument — editing is what it is for, and the ``edit`` mode is the one
    thing this must not get wrong.
    """
    return _EDITOR_NOTICE + build_embed_iframe(base_url, activity, placement, course_id, user_id, "edit", secret, ttl)


class SparkthPxcXBlock(XBlock):
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
        """Render the iframe that loads the activity for a learner, in play mode."""
        return Fragment(
            build_embed_iframe(
                str(settings.SPARKTH_PXC_BASE_URL),
                str(self.activity),
                str(self.placement),
                self._course_id(),
                self._user_id(),
                "play",
                settings.SPARKTH_PXC_LAUNCH_SECRET,
                settings.SPARKTH_PXC_LAUNCH_TOKEN_TTL_SECONDS,
            )
        )

    def studio_view(self, context: dict[str, Any] | None = None) -> Fragment:
        """Render the activity in edit mode for a course author.

        Studio renders this inside its edit modal. That modal's Save and Cancel buttons do not
        apply to the activity's content: the activity persists a change through Sparkth the
        moment the author clicks its own Save, which happens before those buttons are
        reachable. Cancel therefore reverts nothing. The notice in the markup says so, since an
        author has no way to know it otherwise, and ``README.md`` explains why it cannot be
        fixed without putting activity state in two places.
        """
        return Fragment(
            build_editor_html(
                str(settings.SPARKTH_PXC_BASE_URL),
                str(self.activity),
                str(self.placement),
                self._course_id(),
                self._user_id(),
                settings.SPARKTH_PXC_LAUNCH_SECRET,
                settings.SPARKTH_PXC_LAUNCH_TOKEN_TTL_SECONDS,
            )
        )

    def studio_post_duplicate(self, store: Any, source_item: Any) -> bool:
        """Give a block copied with Studio's Duplicate a placement of its own.

        Studio copies every settings field, ``placement`` included, so the copy would otherwise
        share the original's activity data. The copy starts from the activity's defaults.
        Returns ``False``: the block has no children for Studio to copy.
        """
        self._take_new_placement(store)
        return False

    def studio_post_paste(self, store: Any, source_node: Any) -> bool:
        """Give a block pasted from Studio's clipboard a placement of its own.

        The same as ``studio_post_duplicate``, for Copy then Paste.
        """
        self._take_new_placement(store)
        return False

    def _take_new_placement(self, store: Any) -> None:
        """Mint a fresh placement id and save it, since Studio does not save after these hooks."""
        self.placement = str(uuid4())
        self.save()
        # No user id reaches these hooks; edx-platform's own blocks save with None the same way.
        store.update_item(self, None)

    def _course_id(self) -> str:
        """The course this block sits in, from its usage id's course key."""
        course_key = getattr(self.scope_ids.usage_id, "course_key", None)
        return str(course_key) if course_key else ""

    def _user_id(self) -> str:
        """The viewer's Open edX id.

        TODO: An anonymous learner has none, so this collapses to the string "None" and every
        anonymous visitor to a placement shares one identity. Latent today because the bundled
        sample uses activity scope only; closing it needs a product decision on what an
        anonymous visitor should see.
        """
        return str(self.scope_ids.user_id)
