"""The revision directories behind each generated activity, and the atomic swap between them.

Each build or update writes the activity's files into a new revision directory,
``PXC_DATA_DIR/revisions/<id>/<rev>/``. ``generated_activity_dir(id)`` is a relative symlink to the
live one. Replacing that link with ``os.replace`` is atomic, so a reader resolves either the whole
old revision or the whole new one. ``<rev>`` is a uuid7 minted at publish time, so revisions sort by
the time they went live.

A launch is pinned to the revision live when its page rendered: the embed re-signs the launch
token with it, and every later request of that launch reads that revision through
``revision_dir``. So a page never runs one revision's script against another's sandbox.

A plain directory at the link's place becomes the activity's first revision when the activity is next
published. ``prune_revisions`` removes the revisions no launch can still be using.
"""

import itertools
import os
import shutil
import time
from pathlib import Path
from uuid import UUID

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
    target is relative, so the data directory can be mounted anywhere. A plain directory where the
    link belongs becomes the activity's first revision. If the link cannot be made live, the new
    revision and the temporary link are removed and the error is raised.
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


def prune_revisions(activity_id: str, retention_seconds: int) -> None:
    """Remove the revisions of one activity that no launch can still be using.

    A launch is pinned to the revision that was live when its page rendered, by a token minted
    before then and expiring within ``PXC_REVISION_RETENTION_SECONDS``. So once the next newer
    revision has been live for ``retention_seconds`` (that setting), every token pinned to the
    older one has expired.
    The live revision is never removed. A removal that fails is logged and left for the next prune.
    An entry not named like a revision, such as a copy someone left there, is logged and left alone.
    """
    live = generated_activity_dir(activity_id).resolve().name
    cutoff_ms = (time.time() - retention_seconds) * 1000
    revisions = sorted(entry for entry in revisions_dir(activity_id).iterdir() if _is_revision(entry))
    for older, newer in itertools.pairwise(revisions):
        if older.name != live and UUID(newer.name).time <= cutoff_ms:
            try:
                shutil.rmtree(older)
            except OSError as err:
                logger.warning("Could not remove revision %s of PXC activity %s: %s", older.name, activity_id, err)


def _is_revision(entry: Path) -> bool:
    """Whether ``entry`` is named like a revision, by a uuid. Anything else is logged as a warning."""
    try:
        UUID(entry.name)
    except ValueError:
        logger.warning("Skipping %s among the revisions of a PXC activity: its name is not a revision id", entry)
        return False
    return True


def _remove_path(path: Path) -> None:
    """Remove a real directory with its contents, or any other entry, a symlink included. A missing path is skipped."""
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def remove_activity_files(activity_id: UUID) -> None:
    """Remove everything a generated activity keeps on disk.

    That is the link (or a plain directory where it belongs), every revision, the learner state
    file with its ``-wal`` and ``-shm`` sidecars, and the learner file storage. The build's failure
    path and the activity's deletion both call it. It builds the paths itself, so it works whether
    or not the link still exists. Each path is removed on its own: a missing one is skipped, and a
    failure is logged as a warning naming the path and does not stop the rest. Nothing is raised,
    so the caller's own error still propagates.
    """
    name = str(activity_id)
    data_dir = get_pxc_settings().data_dir
    state = data_dir / f"{name}.sqlite3"
    paths = [
        generated_activity_dir(name),
        revisions_dir(name),
        data_dir / "storage" / name,
        *(state.with_name(state.name + suffix) for suffix in ("", "-wal", "-shm")),
    ]
    for path in paths:
        try:
            _remove_path(path)
        except OSError as err:
            logger.warning("Could not remove %s of PXC activity %s: %s", path, name, err)
