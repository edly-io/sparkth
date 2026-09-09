"""Resolve an activity type by name to its source directory and its state file.

An activity type is identified by the ``name`` at the root of its ``manifest.json``. That name
is also its state file's name, so one file holds every course the type appears in and every
learner who answered — the file boundary matches the ``<activity_name>`` segment PXC's own key
scheme starts with.
"""

import json
from pathlib import Path

from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.constants import PXC_ACTIVITY_ROOT
from sparkth.plugins.pxc.exceptions import PxcActivityNotFound, PxcDuplicateActivityName


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
    return get_pxc_settings().data_dir / f"{activity_name}.sqlite3"
