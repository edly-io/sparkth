from __future__ import annotations
"""
Provide API for plugin features.

This module provides the high-level API for working with sparkth-plugins in Sparkth.
"""

import typing as t

from app.hooks import clear_all
from app.hooks.catalog import Actions, Filters
from app.hooks.contexts import Context

# Import modules to trigger hook creation
from . import v1


class PluginError(Exception):
    """Base exception for plugin-related errors."""

    pass


def is_installed(name: str) -> bool:
    """
    Return true if the plugin is installed.

    :param name: Name of the plugin to check
    :return: True if the plugin is installed, False otherwise
    """
    return name in iter_installed()


def iter_installed() -> t.Iterator[str]:
    """
    Iterate on all installed sparkth-plugins, sorted by name.

    This will yield all sparkth-plugins, including those that have the same name.

    The CORE_READY action must have been triggered prior to calling this function,
    otherwise no installed plugin will be detected.

    :return: Iterator of plugin names
    """
    yield from sorted(Filters.PLUGINS_INSTALLED.iterate())


def iter_info() -> t.Iterator[tuple[str, str]]:
    """
    Iterate on the information of all installed sparkth-plugins.

    Yields (plugin_name, info) tuples where info is typically a version string
    or file path.

    :return: Iterator of (plugin_name, info) tuples
    """

    def plugin_info_name(info: tuple[str, str]) -> str:
        return info[0]

    yield from sorted(Filters.PLUGINS_INFO.iterate(), key=plugin_info_name)


def is_loaded(name: str) -> bool:
    """
    Check if a plugin is currently loaded.

    :param name: Name of the plugin to check
    :return: True if the plugin is loaded, False otherwise
    """
    return name in iter_loaded()


def load_all(names: t.Iterable[str]) -> None:
    """
    Load all sparkth-plugins one by one.

    Plugins are loaded in alphabetical order. We ignore sparkth-plugins which failed to load.
    After all sparkth-plugins have been loaded, the PLUGINS_LOADED action is triggered.

    :param names: Iterable of plugin names to load
    """
    names = sorted(set(names))
    for name in names:
        try:
            load(name)
        except Exception as e:
            print(f"Failed to enable plugin '{name}': {e}")
    Actions.PLUGINS_LOADED.do()


def load(name: str) -> None:
    """
    Load a given plugin, thus declaring all its hooks.

    Loading a plugin is done within a context, such that we can remove all hooks when a
    plugin is disabled, or during unit tests.

    :param name: Name of the plugin to load
    :raises PluginError: If the plugin is not installed
    """
    if not is_installed(name):
        raise PluginError(f"Plugin '{name}' is not installed.")

    with Context("sparkth-plugins").enter():
        with Context(f"plugin:{name}").enter():
            Actions.PLUGIN_LOADED.do(name)
            Filters.PLUGINS_LOADED.add_item(name)


def iter_loaded() -> t.Iterator[str]:
    """
    Iterate on the list of loaded plugin names, sorted in alphabetical order.

    Note that loaded plugin names are deduplicated. Thus, if two sparkth-plugins have
    the same name, just one name will be displayed.

    :return: Iterator of loaded plugin names
    """
    plugins: t.Iterable[str] = Filters.PLUGINS_LOADED.iterate()
    yield from sorted(set(plugins))


def unload(plugin: str) -> None:
    """
    Remove all filters and actions associated to a given plugin.

    :param plugin: Name of the plugin to unload
    """
    clear_all(context=f"plugin:{plugin}")


@Actions.PLUGIN_UNLOADED.add()
def _unload_on_disable(plugin: str) -> None:
    """
    Automatically unload a plugin when the PLUGIN_UNLOADED action is triggered.

    :param plugin: Name of the plugin to unload
    """
    unload(plugin)


def discover_plugins() -> None:
    """
    Trigger plugin discovery.

    This will call the CORE_READY action which causes all sparkth-plugins to be discovered
    from entrypoints and local files.
    """
    Actions.CORE_READY.do()


__all__ = [
    "PluginError",
    "is_installed",
    "iter_installed",
    "iter_info",
    "is_loaded",
    "load_all",
    "load",
    "iter_loaded",
    "unload",
    "discover_plugins",
]
