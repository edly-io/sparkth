
"""
Version 1 plugin discovery and loading.

This module handles the discovery of sparkth-plugins from:
- Python packages with "sparkth.plugin.v1" entrypoints
- Local .py files in the sparkth-plugins directory
"""

import importlib.util
import os
import sys
from glob import glob
from typing import TYPE_CHECKING

import importlib_metadata

from app.hooks.catalog import Actions, Filters
from app.hooks.contexts import Context, Contextualized

from .base import PLUGINS_ROOT

if TYPE_CHECKING:
    pass


@Actions.CORE_READY.add()
def _discover_module_plugins() -> None:
    """
    Discover .py files in the sparkth-plugins root folder.

    This runs when the application core is ready and discovers all
    local plugin files.
    """
    with Context("sparkth-plugins").enter():
        for path in glob(os.path.join(PLUGINS_ROOT, "*.py")):
            discover_module(path)


@Actions.CORE_READY.add()
def _discover_entrypoint_plugins() -> None:
    """
    Discover all sparkth-plugins that declare a "sparkth.plugin.v1" entrypoint.

    This runs when the application core is ready and discovers all
    sparkth-plugins installed as Python packages.
    """
    with Context("sparkth-plugins").enter():
        if "SPARKTH_IGNORE_ENTRYPOINT_PLUGINS" not in os.environ:
            for entrypoint in importlib_metadata.entry_points(
                group="sparkth.plugin.v1"
            ):
                discover_package(entrypoint)


def discover_module(path: str) -> None:
    """
    Install a plugin written as a single file module.

    :param path: Path to the plugin .py file
    """
    name = os.path.splitext(os.path.basename(path))[0]

    # Add plugin to the list of installed sparkth-plugins
    Filters.PLUGINS_INSTALLED.add_item(name)

    # Add plugin information
    Filters.PLUGINS_INFO.add_item((name, path))

    # Import module on enable
    @Actions.PLUGIN_LOADED.add()
    def load(plugin_name: str) -> None:
        if name == plugin_name:
            # https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
            spec = importlib.util.spec_from_file_location(
                f"sparkth.plugin.v1.{name}", path
            )
            if spec is None or spec.loader is None:
                raise ValueError(f"Plugin could not be found: {path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)


def discover_package(entrypoint: importlib_metadata.EntryPoint) -> None:
    """
    Install a plugin from a python package.

    :param entrypoint: The entrypoint object for the plugin
    """
    name = entrypoint.name

    # Add plugin to the list of installed sparkth-plugins
    Filters.PLUGINS_INSTALLED.add_item(name)

    # Add plugin information
    if entrypoint.dist is None:
        raise ValueError(f"Could not read plugin version: {name}")
    dist_version = entrypoint.dist.version if entrypoint.dist else "Unknown"
    Filters.PLUGINS_INFO.add_item((name, dist_version))

    @Actions.PLUGIN_LOADED.add()
    def load(plugin_name: str) -> None:
        """
        Import module on enable.
        """
        if name == plugin_name:
            importlib.import_module(entrypoint.value)

    # Remove module from cache on disable
    @Actions.PLUGIN_UNLOADED.add()
    def unload(plugin_name: str) -> None:
        """
        Remove plugin module from import cache on disable.

        This is necessary in one particular use case: when a plugin is enabled,
        disabled, and enabled again -- all within the same call to Sparkth. In such a
        case, the following happens:

        1. plugin enabled: the plugin module is imported. It is automatically added by
           Python to the import cache.
        2. plugin disabled: action and filter callbacks are removed, but the module
           remains in the import cache.
        3. plugin enabled again: the plugin module is imported. But because it's in the
           import cache, the module instructions are not executed again.

        This is not supposed to happen when we run Sparkth normally from the CLI. But when
        running a long-lived process, such as a web app, where a plugin might be enabled
        and disabled multiple times, this becomes an issue.
        """
        if name == plugin_name and entrypoint.value in sys.modules:
            sys.modules.pop(entrypoint.value)
