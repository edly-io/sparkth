"""The ``"pxc"`` content contributor: what an LMS-publishing plugin asks for.

Building a placement names an activity type and mints an id for it. That id is the only thing
the course holds about the placement, and nothing about it is persisted here — no state, no
table, no migration (D4).

Nothing about any particular activity appears here, deliberately. An activity's initial
configuration is declared by the activity, as the defaults on its manifest's fields, which the
runtime serves for any placement nobody has configured yet. Writing that configuration from
here would mean knowing which fields a given activity declares, and no contributor can know
that for every activity it might place.

One bundled activity is named for every request, by design (L5). An authoring module comes
later; when it does, the values it writes are what take over from those defaults.
"""

from uuid6 import uuid7

from sparkth.lib.content.exceptions import ContentBuildError
from sparkth.lib.content.hooks import ContentBlock
from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.activities import activity_dir
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.constants import PXC_BLOCK_CATEGORY
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound

logger = get_logger(__name__)


async def build_pxc_block(course_id: str) -> ContentBlock:
    """Mint a placement in ``course_id`` and describe the block that carries it.

    ``course_id`` is unused: a placement id is unique on its own and the course is already
    known to the caller. The parameter is the contributor hook's signature, which every
    contributor shares whether or not it needs one.

    Raises:
        ContentBuildError: if ``PXC_DEFAULT_ACTIVITY`` names no bundled activity. Checked here
            rather than left to fail at launch, so a misconfigured deployment is refused while
            an author is still looking at the screen.
    """
    activity = get_pxc_settings().default_activity
    try:
        activity_dir(activity)
    except PxcActivityNotFound as err:
        logger.error("PXC_DEFAULT_ACTIVITY names an unknown activity %r: %s", activity, err)
        raise ContentBuildError(f"PXC_DEFAULT_ACTIVITY names an unknown activity: {activity!r}") from err

    placement = str(uuid7())
    logger.info("Placed PXC activity %s as placement %s in course %s", activity, placement, course_id)
    return ContentBlock(
        "PXC Activity",
        PXC_BLOCK_CATEGORY,
        {"activity": activity, "placement": placement},
    )
