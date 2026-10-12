"""The revision directories behind each generated activity, and the atomic swap between them.

Each build or update writes the activity's files into a new revision directory,
``PXC_DATA_DIR/revisions/<id>/<rev>/``. ``generated_activity_dir(id)`` is a relative symlink to the
live one. Replacing that link with ``os.replace`` is atomic, so a reader resolves either the whole
old revision or the whole new one. ``<rev>`` is a uuid7 minted at publish time, so revisions sort by
the time they went live.

A launch is pinned to the revision live when its page rendered: the embed re-signs the launch
token with it, and every later request of that launch reads that revision through
``revision_dir``. So a page never runs one revision's script against another's sandbox.
"""

import os
import shutil
from pathlib import Path

from uuid6 import uuid7

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.activities import activity_dir, generated_activity_dir, parse_activity_id
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound

logger = get_logger(__name__)


def revisions_dir(activity_id: str) -> Path:
    """Where every revision of one generated activity lives."""
    return get_pxc_settings().data_dir / "revisions" / activity_id


def live_revision(activity_name: str) -> str | None:
    """The id of the activity's live revision, or None for an activity kept outside revisions, such as a bundled one.

    Raises:
        PxcActivityNotFound: if no activity goes by this name.
    """
    directory = activity_dir(activity_name)
    return directory.name if directory.parent == revisions_dir(activity_name).resolve() else None


def revision_dir(activity_id: str, revision: str) -> Path:
    """The directory of one revision of a generated activity, live or replaced.

    Raises:
        PxcActivityNotFound: if either id is not a canonical UUID, or the revision is not on disk.
    """
    directory = revisions_dir(str(parse_activity_id(activity_id))) / str(parse_activity_id(revision))
    if not (directory / "manifest.json").is_file():
        raise PxcActivityNotFound(f"Unknown revision {revision} of activity {activity_id}")
    return directory


def publish_revision(staged: Path, activity_id: str) -> Path:
    """Move a staged activity into a new revision, make that revision live, and return it.

    ``staged`` must sit on the data directory's filesystem, so moving it is a rename. The link's
    target is relative, so the data directory can be mounted anywhere. If the link cannot be made
    live, the new revision and the temporary link are removed, the live revision is untouched, and
    the error is raised.
    """
    revision = revisions_dir(activity_id) / str(uuid7())
    revision.parent.mkdir(parents=True, exist_ok=True)
    staged.rename(revision)
    link = generated_activity_dir(activity_id)
    link.parent.mkdir(parents=True, exist_ok=True)
    temporary = link.with_name(f".{activity_id}.{revision.name}")
    try:
        temporary.symlink_to(Path("..") / "revisions" / activity_id / revision.name)
        os.replace(temporary, link)
    except OSError as err:
        logger.error(
            "Could not make revision %s of PXC activity %s live; removing it: %s", revision.name, activity_id, err
        )
        temporary.unlink(missing_ok=True)
        shutil.rmtree(revision)
        raise
    return revision


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
