
"""
Base plugin configuration and utilities.

This module provides the base configuration for the plugin system,
including the location where sparkth-plugins are stored.
"""

import os
from pathlib import Path

# Default sparkth-plugins directory in project root
PLUGINS_ROOT_ENV_VAR = "SPARKTH_PLUGINS_ROOT"

# Get the project root directory (where pyproject.toml is located)
_current_file = Path(__file__).resolve()
_project_root = _current_file.parent.parent.parent  # app/plugins/base.py -> project root

DEFAULT_PLUGINS_ROOT = os.path.join(str(_project_root), "sparkth-plugins")

# Get the sparkth-plugins root directory from environment or use default
PLUGINS_ROOT = os.environ.get(PLUGINS_ROOT_ENV_VAR, DEFAULT_PLUGINS_ROOT)


def get_plugins_root() -> str:
    """
    Get the root directory where local sparkth-plugins are stored.

    By default, this is ~/.sparkth/sparkth-plugins, but it can be overridden
    by setting the SPARKTH_PLUGINS_ROOT environment variable.

    :return: Absolute path to the sparkth-plugins root directory
    """
    return PLUGINS_ROOT


def ensure_plugins_root() -> None:
    """
    Ensure that the sparkth-plugins root directory exists.

    Creates the directory if it doesn't exist.
    """
    plugins_dir = Path(get_plugins_root())
    plugins_dir.mkdir(parents=True, exist_ok=True)
