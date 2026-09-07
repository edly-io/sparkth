"""The ``"pxc"`` content contributor: what an LMS-publishing plugin asks for.

Building a placement mints an id, seeds the bundled sample's configuration into the activity
type's state file under that id, and returns the block to create. The placement id is the only
thing the course holds about it — nothing about a placement is persisted here, so there is no
table and no migration (D4).

One bundled activity is seeded for every request, by design (L5). An authoring module comes
later; when it does, the configuration seeded below is what it replaces.
"""

import sqlite3

from uuid6 import uuid7

from sparkth.lib.content.exceptions import ContentBuildError
from sparkth.lib.content.hooks import ContentBlock
from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.activities import state_file
from sparkth.plugins.pxc.constants import PXC_BLOCK_CATEGORY, PXC_DEFAULT_ACTIVITY
from sparkth.plugins.pxc.field_store import SqliteFieldStore

logger = get_logger(__name__)

# The bundled sample's configuration. Activity-scoped fields, which is all the sample uses.
_SAMPLE_QUESTION = "What is 2 + 2?"
_SAMPLE_ANSWERS = ["3", "4", "5"]
_SAMPLE_CORRECT_ANSWERS = [1]


async def build_pxc_block(course_id: str) -> ContentBlock:
    """Mint a placement in ``course_id``, seed its configuration, and describe its block.

    Raises:
        ContentBuildError: if the activity type's state file cannot be written.
    """
    placement = str(uuid7())

    # Activity-scoped fields: the learner segment of the key is blank, which is how the runtime
    # reads them back for every learner of this placement.
    scope = (course_id, PXC_DEFAULT_ACTIVITY, placement, "")
    try:
        store = SqliteFieldStore(state_file(PXC_DEFAULT_ACTIVITY))
        store.set(*scope, "question", _SAMPLE_QUESTION)
        store.set(*scope, "answers", _SAMPLE_ANSWERS)
        store.set(*scope, "correct_answers", _SAMPLE_CORRECT_ANSWERS)
    except (sqlite3.Error, OSError) as err:
        logger.error("Seeding PXC placement %s for course %s failed: %s", placement, course_id, err)
        raise ContentBuildError(f"Could not seed the {PXC_DEFAULT_ACTIVITY} activity's state") from err

    logger.info("Seeded PXC activity %s placement %s for course %s", PXC_DEFAULT_ACTIVITY, placement, course_id)
    return ContentBlock(
        PXC_BLOCK_CATEGORY,
        "PXC Activity",
        {"activity": PXC_DEFAULT_ACTIVITY, "placement": placement},
    )
