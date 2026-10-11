"""The revision directories behind each generated activity, and the atomic swap between them.

Each build or update writes the activity's files into a new revision directory,
``PXC_DATA_DIR/revisions/<id>/<rev>/``. ``generated_activity_dir(id)`` is a relative symlink to the
live one. Replacing that link with ``os.replace`` is atomic, so a reader resolves either the whole
old revision or the whole new one. ``<rev>`` is a uuid7 minted at publish time, so revisions sort by
the time they went live.

A plain directory at the link's place becomes the activity's first revision when the activity is next
published. ``prune_revisions`` removes the revisions no runtime can still be using.
"""

import itertools
import os
import shutil
import time
from pathlib import Path
from uuid import UUID

from uuid6 import uuid7

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.activities import generated_activity_dir
from sparkth.plugins.pxc.config import get_pxc_settings

logger = get_logger(__name__)


def revisions_dir(activity_id: str) -> Path:
    """Where every revision of one generated activity lives."""
    return get_pxc_settings().data_dir / "revisions" / activity_id


def publish_revision(staged: Path, activity_id: str) -> Path:
    """Move a staged activity into a new revision, make that revision live, and return it.

    ``staged`` must sit on the data directory's filesystem, so moving it is a rename. The link's
    target is relative, so the data directory can be mounted anywhere. A plain directory where the
    link belongs becomes the activity's first revision.
    """
    revisions = revisions_dir(activity_id)
    revisions.mkdir(parents=True, exist_ok=True)
    link = generated_activity_dir(activity_id)
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_dir() and not link.is_symlink():
        # A launch between this rename and the link replace below gets a 404.
        link.rename(revisions / str(uuid7()))
    revision = revisions / str(uuid7())
    staged.rename(revision)
    temporary = link.with_name(f".{activity_id}.{revision.name}")
    temporary.symlink_to(Path("..") / "revisions" / activity_id / revision.name)
    os.replace(temporary, link)
    return revision


def prune_revisions(activity_id: str, retention_seconds: int) -> None:
    """Remove the revisions of one activity that no runtime can still be using.

    A runtime is pinned to the revision that was live when it was built, from a launch token
    minted before then. So once the next newer revision has been live for ``retention_seconds``,
    which is at least the longest launch-token lifetime, every token that could reach the older
    one has expired. The live revision is never removed. A removal that fails is logged and left
    for the next prune.
    """
    live = generated_activity_dir(activity_id).resolve().name
    cutoff_ms = (time.time() - retention_seconds) * 1000
    for older, newer in itertools.pairwise(sorted(revisions_dir(activity_id).iterdir())):
        if older.name != live and UUID(newer.name).time <= cutoff_ms:
            try:
                shutil.rmtree(older)
            except OSError as err:
                logger.warning("Could not remove revision %s of PXC activity %s: %s", older.name, activity_id, err)


def remove_activity_files(activity_id: str) -> None:
    """Remove a generated activity's link and every revision of it.

    A failure is logged as a warning and the files it could not remove are left in place. It is
    not raised, so the caller's own error still propagates.
    """
    revisions = revisions_dir(activity_id)
    try:
        generated_activity_dir(activity_id).unlink(missing_ok=True)
        if revisions.exists():
            shutil.rmtree(revisions)
    except OSError as err:
        logger.warning("Could not remove the files of PXC activity %s: %s", activity_id, err)
