"""The ``"pxc"`` content contributor: what an LMS-publishing plugin asks for.

Building an activity instance names an activity and mints an id for it. That id is the only thing the
course holds about the activity instance, and nothing about it is persisted here: no state, no table.

The options are the activities the user may place in their course.

Nothing about any particular activity's content appears here. An activity declares its initial
configuration as the defaults on its manifest's fields, and the runtime serves those for any
activity instance nobody has configured yet.
"""

from uuid6 import uuid7

from sparkth.lib.auth import current_user_id
from sparkth.lib.content.exceptions import ContentBuildError
from sparkth.lib.content.hooks import ContentBlock, ContentOption
from sparkth.lib.db import session_scope
from sparkth.lib.exceptions.auth import NoAuthenticatedUser
from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.activities import activity_names, parse_activity_id
from sparkth.plugins.pxc.constants import PXC_BLOCK_CATEGORY, PXC_MAX_PLACEABLE_ACTIVITIES
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound
from sparkth.plugins.pxc.store import get_owned_activity, list_owned_activities

logger = get_logger(__name__)


async def list_pxc_options() -> list[ContentOption]:
    """The activities the caller may place: every bundled one, then the caller's newest own.

    The caller's own are capped at ``PXC_MAX_PLACEABLE_ACTIVITIES``, since every option reaches
    the model. An older one is still placeable by its id.

    With nobody authenticated only the bundled activities are offered, so listing contributors
    keeps working for a caller that carries no identity.
    """
    bundled = [ContentOption(name, name) for name in activity_names()]
    try:
        owner_user_id = current_user_id()
    except NoAuthenticatedUser as err:
        logger.info("Listing PXC options with no authenticated user, bundled only: %s", err)
        return bundled
    async with session_scope() as session:
        owned = await list_owned_activities(session, owner_user_id, PXC_MAX_PLACEABLE_ACTIVITIES)
    return bundled + [ContentOption(str(activity.id), activity.title) for activity in owned]


async def build_pxc_block(course_id: str, activity_id: str | None) -> ContentBlock:
    """Mint an activity instance in ``course_id`` for the chosen activity, and describe its block.

    The block is titled after the activity: a generated one's title, or a bundled one's name.

    ``activity_id`` is the hook's ``option_id``: a bundled activity's name or one of the
    caller's generated activity ids. There is no default activity, so ``None`` places nothing.
    ``course_id`` is unused: an activity instance id is unique on its own, and the parameter is
    the contributor hook's shared signature.

    Raises:
        ContentBuildError: if no activity was chosen, or the chosen activity is unknown or not
            the caller's own.
    """
    if activity_id is None:
        logger.warning("Refused to place a PXC activity in course %s: none was chosen", course_id)
        raise ContentBuildError("Choose an activity to place: pass one of the contributor's options")
    activity = await placeable_activity(activity_id)
    activity_instance = str(uuid7())
    logger.info(
        "Placed PXC activity %s as activity_instance %s in course %s", activity.id, activity_instance, course_id
    )
    return ContentBlock(
        activity.label, PXC_BLOCK_CATEGORY, {"activity": activity.id, "activity_instance": activity_instance}
    )


async def placeable_activity(activity_id: str) -> ContentOption:
    """The activity an activity instance carries for ``activity_id``, if the caller may place it.

    Returned as the option the caller chose: its id, and its label, which titles the block.

    A bundled name is open to everyone. Anything else must be a generated activity owned by the
    authenticated caller. An unknown id, a malformed one, someone else's and an anonymous
    caller all get one message, which does not reveal whether the activity exists.

    Raises:
        ContentBuildError: if the caller may not place this activity.
    """
    if activity_id in activity_names():
        return ContentOption(activity_id, activity_id)
    try:
        generated_id = parse_activity_id(activity_id)
        owner_user_id = current_user_id()
        async with session_scope() as session:
            activity = await get_owned_activity(session, generated_id, owner_user_id)
    except (PxcActivityNotFound, NoAuthenticatedUser) as err:
        logger.warning("Refused to place PXC activity %r: %s", activity_id, err)
        raise ContentBuildError(f"No activity you can place has the id {activity_id!r}") from err
    return ContentOption(str(activity.id), activity.title)
