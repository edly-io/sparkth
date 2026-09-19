"""Resolve an activity type by name to its source directory, its manifest and its state file.

An activity type is identified by the ``name`` at the root of its ``manifest.json``. That name
is also its state file's name, so one file holds every course the type appears in and every
learner who answered — the file boundary matches the ``<activity_name>`` segment PXC's own key
scheme starts with.
"""

import json
from functools import cache
from pathlib import Path

from pxc.lib.manifest_types import PxcActivityManifest

from sparkth.lib.log import get_logger
from sparkth.plugins.pxc.constants import PXC_ACTIVITY_ROOT, PXC_DATA_DIR
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


def activity_dir(activity_name: str) -> Path:
    """The source directory of one activity type.

    Raises:
        PxcActivityNotFound: if no bundled activity goes by this name.
    """
    directory = _ACTIVITIES.get(activity_name)
    if directory is None:
        raise PxcActivityNotFound(f"Unknown activity type: {activity_name}")
    return directory


def state_file(activity_name: str) -> Path:
    """The SQLite file holding every learner's state for one activity type.

    Raises:
        PxcActivityNotFound: if no bundled activity goes by this name — also rejects a
            path-escaping name, since it can never match an indexed activity.
    """
    activity_dir(activity_name)
    return PXC_DATA_DIR / f"{activity_name}.sqlite3"


@cache
def activity_manifest(activity_name: str) -> PxcActivityManifest:
    """The parsed manifest of one activity type.

    Cached for the life of the process, on the same assumption as the index above: the bundled
    activities do not change at runtime.

    Raises:
        PxcActivityNotFound: if no bundled activity goes by this name.
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
        PxcActivityNotFound: if no bundled activity goes by this name.
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
