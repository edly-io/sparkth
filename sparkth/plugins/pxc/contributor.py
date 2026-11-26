"""The ``"pxc"`` content contributor: what an LMS-publishing plugin asks for.

Building an activity instance names an activity and mints an id for it. That id is the only thing the
course holds about the activity instance. For a generated activity, Sparkth records the time it was
first placed in a course, once the LMS has created its block.

The options are the activities the user may place in their course: the bundled ones, and the user's
own when they hold ``pxc.activity.place`` over them.

Nothing about any particular activity's content appears here. An activity declares its initial
configuration as the defaults on its manifest's fields, and the runtime serves those for any
activity instance nobody has configured yet.
"""

from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from uuid6 import uuid7

from sparkth.lib.auth import current_user_id
from sparkth.lib.content.exceptions import ContentBuildError, ContentPlacementError
from sparkth.lib.content.hooks import ContentBlock, ContentOption
from sparkth.lib.db import session_scope
from sparkth.lib.exceptions.auth import NoAuthenticatedUser
from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.activities import activity_dir, activity_names
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.constants import PXC_BLOCK_CATEGORY
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound, PxcActivityNotPermitted
from sparkth.plugins.pxc.permissions import PXC_ACTIVITY_PLACE, get_permitted_activity, has_activity_permission
from sparkth.plugins.pxc.store import list_owned_activities, mark_placed

logger = get_logger(__name__)


async def list_pxc_options() -> list[ContentOption]:
    """The activities the caller may place: every bundled one, then the caller's newest own.

    The caller's own are offered only when they hold ``pxc.activity.place`` at their own user
    scope; a caller without it gets the bundled activities, and nothing is recorded. They are
    capped at ``PXC_LIST_ACTIVITIES_LIMIT``, since every option reaches the model. Each is
    labelled with its title and build time in UTC, which tells apart activities that share a
    title.

    With nobody authenticated only the bundled activities are offered, so listing contributors
    keeps working for a caller that carries no identity.
    """
    bundled = [ContentOption(name, name) for name in activity_names()]
    try:
        user_id = current_user_id()
    except NoAuthenticatedUser as err:
        logger.info("Listing PXC options with no authenticated user, bundled only: %s", err)
        return bundled
    async with session_scope() as session:
        # The caller is offered their own activities, so the owner and the caller are the same user.
        if not await has_activity_permission(session, PXC_ACTIVITY_PLACE, user_id, user_id):
            return bundled
        owned = await list_owned_activities(session, user_id, get_pxc_settings().list_activities_limit)
    return bundled + [
        ContentOption(str(activity.id), f"{activity.title} ({activity.created_at:%Y-%m-%d %H:%M} UTC)")
        for activity in owned
    ]


async def build_pxc_block(course_id: str, activity_id: str | None) -> ContentBlock:
    """Mint an activity instance in ``course_id`` for the chosen activity, and describe its block.

    The block is titled after the activity: a generated one's title, or a bundled one's name.
    Nothing is recorded here: the LMS may still refuse the block, so the placement callback records it
    once the block exists.

    ``activity_id`` is the hook's ``option_id``: a bundled activity's name or the id of a
    generated activity the caller may place. There is no default activity, so ``None`` places nothing.
    ``course_id`` is unused: an activity instance id is unique on its own, and the parameter is
    the contributor hook's shared signature.

    Raises:
        ContentBuildError: if no activity was chosen, or the chosen activity is unknown or the
            caller may not place it.
    """
    if activity_id is None:
        logger.warning("Refused to place a PXC activity in course %s: none was chosen", course_id)
        raise ContentBuildError("Choose an activity to place: pass one of the contributor's options")
    activity = await placeable_activity(activity_id)
    activity_instance = str(uuid7())
    logger.info(
        "Built a block for PXC activity %s as activity_instance %s in course %s",
        activity.id,
        activity_instance,
        course_id,
    )
    return ContentBlock(
        activity.label, PXC_BLOCK_CATEGORY, {"activity": activity.id, "activity_instance": activity_instance}
    )


async def record_pxc_placement(activity_id: str | None) -> None:
    """Record that a generated activity sits in a course, unless an earlier placement already did.

    The publishing plugin awaits this once the LMS has created the block. ``activity_id`` is the
    option id the block was built from. A bundled activity has nothing to record.

    Raises:
        ContentPlacementError: if the database cannot record the placement.
    """
    if activity_id is None or activity_id in activity_names():
        return
    try:
        async with session_scope() as session:
            await mark_placed(session, UUID(activity_id))
    except SQLAlchemyError as err:
        logger.error("Could not record that PXC activity %s was placed: %s", activity_id, err)
        raise ContentPlacementError(f"Could not record that activity {activity_id} was placed") from err


async def placeable_activity(activity_id: str) -> ContentOption:
    """The activity an activity instance carries for ``activity_id``, if the caller may place it.

    Returned as the option the caller chose: its id, and its label, which titles the block.

    A bundled name is open to everyone. Anything else must be a generated activity the authenticated
    caller holds ``pxc.activity.place`` for at its owner's user scope, with its files still on disk.
    An unknown id, a malformed one, one the caller may not place, one whose files are gone and an
    anonymous caller all get one message, which does not reveal whether the activity exists. A
    refusal for lack of the permission is recorded as a denial; an unknown id records nothing.

    Raises:
        ContentBuildError: if the caller may not place this activity.
    """
    if activity_id in activity_names():
        return ContentOption(activity_id, activity_id)
    try:
        activity = await get_permitted_activity(activity_id, PXC_ACTIVITY_PLACE)
        activity_dir(str(activity.id))
    except (PxcActivityNotFound, PxcActivityNotPermitted, NoAuthenticatedUser) as err:
        logger.warning("Refused to place PXC activity %r: %s", activity_id, err)
        raise ContentBuildError(f"No activity you can place has the id {activity_id!r}") from err
    return ContentOption(str(activity.id), activity.title)
