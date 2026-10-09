"""Resolve an activity by name to its source directory, its manifest and its state file.

Two kinds of activity resolve here. A bundled activity ships in ``activities/`` and is named by
the ``name`` at the root of its ``manifest.json``. A generated activity was built by an author.
Its name is its id, and its files live under ``generated_activity_dir(id)``. The name is also
the state file's name, so one file holds every course the activity appears in and every learner
who answered. That file boundary matches the ``<activity_name>`` segment PXC's own key scheme
starts with.
"""

import json
from functools import cache
from pathlib import Path
from uuid import UUID

from pxc.lib.manifest_types import PxcActivityManifest

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.constants import PXC_ACTIVITY_ROOT
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound, PxcAssetNotFound, PxcDuplicateActivityName

logger = get_logger(__name__)


def index_activities(root: Path) -> dict[str, Path]:
    """Map every activity name under ``root`` to its directory.

    Raises:
        PxcDuplicateActivityName: if two directories declare the same name.
        KeyError: if a manifest has no ``"name"`` key.
        json.JSONDecodeError: if a manifest is not valid JSON.
    """
    index: dict[str, Path] = {}
    for manifest_path in sorted(root.glob("*/manifest.json")):
        name = str(json.loads(manifest_path.read_text(encoding="utf-8"))["name"])
        if name in index:
            raise PxcDuplicateActivityName(
                f"Activity name {name!r} is declared by both {index[name].name} and {manifest_path.parent.name}"
            )
        index[name] = manifest_path.parent
    return index


# Built once at import: the bundled activities do not change at runtime.
_ACTIVITIES = index_activities(PXC_ACTIVITY_ROOT)


def activity_names() -> list[str]:
    """The names of every bundled activity type."""
    return sorted(_ACTIVITIES)


def generated_activity_dir(activity_id: str) -> Path:
    """Where a generated activity's files live, whether or not it has been built yet."""
    return get_pxc_settings().data_dir / "activities" / activity_id


def activity_dir(activity_name: str) -> Path:
    """The source directory of one activity: a bundled one by name, else a generated one by id.

    Bundled activities are looked up first. A generated activity resolves from its directory
    alone, so a learner's launch needs no database read.

    Raises:
        PxcActivityNotFound: if no bundled activity goes by this name and no generated activity
            has been built under it.
    """
    directory = _ACTIVITIES.get(activity_name)
    if directory is not None:
        return directory
    generated = generated_activity_dir(str(parse_activity_id(activity_name)))
    if (generated / "manifest.json").is_file():
        return generated
    raise PxcActivityNotFound(f"Unknown activity type: {activity_name}")


def preview_url(activity_id: UUID) -> str:
    """The Sparkth page that previews one generated activity, relative to the frontend's root."""
    return f"/dashboard/pxc?activity={activity_id}"


def state_file(activity_name: str) -> Path:
    """The SQLite file holding every learner's state for one activity.

    Raises:
        PxcActivityNotFound: if no bundled or generated activity goes by this name. That also
            rejects a path-escaping name, which can never match one.
    """
    activity_dir(activity_name)
    return get_pxc_settings().data_dir / f"{activity_name}.sqlite3"


@cache
def activity_manifest(activity_name: str) -> PxcActivityManifest:
    """The parsed manifest of one activity.

    Cached for the life of the process. Neither kind of activity changes once written: the
    bundled ones ship with the code, and a generated one is never rebuilt in place.

    Raises:
        PxcActivityNotFound: if no activity goes by this name.
    """
    manifest_path = activity_dir(activity_name) / "manifest.json"
    return PxcActivityManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))


def asset_path(activity_name: str, file_path: str) -> Path:
    """The file behind one asset URL: the activity's UI script, or one asset it declares.

    An exact match against the manifest is what keeps a request inside the activity directory.
    The manifest schema constrains ``ui`` and every asset to a relative path free of ``..``, so
    a path that matches one of them cannot escape, and one that matches none is refused before
    it is ever joined.

    Raises:
        PxcActivityNotFound: if no activity goes by this name.
        PxcAssetNotFound: if the manifest does not declare the file, or it is missing on disk.
    """
    manifest = activity_manifest(activity_name)
    if file_path not in {manifest.ui, *(asset.root for asset in manifest.assets or [])}:
        logger.warning("Refused undeclared asset %s of activity %s", file_path, activity_name)
        raise PxcAssetNotFound(f"No such asset: {file_path}")
    path = activity_dir(activity_name) / file_path
    if not path.is_file():
        logger.warning("Declared asset %s of activity %s is missing on disk", file_path, activity_name)
        raise PxcAssetNotFound(f"No such asset: {file_path}")
    return path


def parse_activity_id(activity_id: str) -> UUID:
    """Parse the id of a generated activity, accepted only in its canonical spelling.

    One spelling per activity keeps its state in one place. No path-escaping text parses, so a
    parsed id never leaves the activities directory.

    Raises:
        PxcActivityNotFound: if the text is not a UUID in its canonical spelling. A malformed id
            reads like any other unknown one.
    """
    try:
        parsed = UUID(activity_id)
    except ValueError as err:
        logger.info("Refused a malformed activity id %r: %s", activity_id, err)
        raise PxcActivityNotFound(f"Unknown activity: {activity_id}") from err
    if str(parsed) != activity_id:
        logger.info("Refused a non-canonical activity id %r", activity_id)
        raise PxcActivityNotFound(f"Unknown activity: {activity_id}")
    return parsed
