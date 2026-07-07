"""
Plugin loader for Sparkth.

Manages plugin discovery and instantiation.
"""

import importlib
import inspect
import re
from typing import Iterator, Type

from sparkth.core.config import get_plugin_settings
from sparkth.core.plugins.base import SparkthPlugin
from sparkth.core.plugins.exceptions import (
    PluginLoadError,
    PluginValidationError,
)
from sparkth.lib.log import get_logger

logger = get_logger(__name__)


class PluginLoader:
    """
    Central SparkthPlugin class loader and instantiator.

    The list of plugins is parsed from the plugin settings. Then, each class is
    instantiated and the corresponding object are stored in the loader instance.
    """

    INSTANCE: "PluginLoader" | None = None

    @classmethod
    def instance(cls) -> "PluginLoader":
        """
        Load class instance from singleton.
        """
        if cls.INSTANCE is None:
            cls.INSTANCE = cls()
        return cls.INSTANCE

    def __init__(self) -> None:
        """Load all plugins on init."""
        self._loaded_plugins: dict[str, SparkthPlugin] = {}
        self._load_all()

    def _load_all(self) -> None:
        """
        Load all plugins from configuration.

        Note:
            Continues loading other plugins if one fails.
            Check logs for any failures.
        """
        for plugin_name, plugin_class in self.iter_plugin_classes():
            try:
                plugin_instance = plugin_class(plugin_name)
            except Exception as e:
                # We catch a broad exception here because we don't want failing plugins
                # to crash the app.
                logger.error(f"Failed to load plugin '{plugin_name}'")
                logger.exception(e)
                continue
            self._loaded_plugins[plugin_name] = plugin_instance

    def iter_plugin_classes(self) -> Iterator[tuple[str, Type[SparkthPlugin]]]:
        """
        Discover all plugins defined in get_plugin_settings().

        Yields:
            (name, class) tuples

        Note:
            All plugins are enabled by default.
            Format: "module.path:ClassName"
        """
        for module_string in get_plugin_settings():
            try:
                plugin_name, plugin_class = _load_plugin_class(module_string)
            except (PluginLoadError, PluginValidationError) as e:
                logger.warning(f"Failed to discover plugin from '{module_string}'")
                logger.exception(e)
                continue
            yield (plugin_name, plugin_class)

    def get_loaded_plugins(self) -> list[tuple[str, SparkthPlugin]]:
        """
        Get all loaded plugin instances.

        Returns:
            List where plugins are sorted in alphabetical order.
        """
        return list(sorted(self._loaded_plugins.items()))

    def unload_all(self) -> None:
        """Unload all currently loaded plugins."""
        self._loaded_plugins = {}


def _load_plugin_class(module_string: str) -> tuple[str, Type[SparkthPlugin]]:
    """
    Load a plugin class from module string.

    Args:
        module_string: Module string in format "module.path:ClassName"

    Returns:
        Tuple of (plugin_name, plugin_class)

    Raises:
        PluginLoadError: If plugin cannot be loaded
        PluginValidationError: If plugin is invalid

    Note:
        Expected format: "module.path:ClassName"
        Example: "sparkth.plugins.canvas.plugin:CanvasPlugin"
    """
    if ":" not in module_string:
        raise PluginLoadError(f"Invalid module format. Expected 'module.path:ClassName', got '{module_string}'")

    module_name, class_name = module_string.split(":", 1)
    module_name = module_name.strip()
    class_name = class_name.strip()

    if not module_name or not class_name:
        raise PluginLoadError(f"Empty module or class name in '{module_string}'")

    try:
        module = importlib.import_module(module_name)
    except ImportError as e:
        raise PluginLoadError(f"Failed to import module '{module_name}': {e}") from e

    if not hasattr(module, class_name):
        raise PluginLoadError(f"Class '{class_name}' not found in module '{module_name}'")

    plugin_class = getattr(module, class_name)

    if not (inspect.isclass(plugin_class) and issubclass(plugin_class, SparkthPlugin)):
        raise PluginValidationError(f"Class '{class_name}' must be a subclass of SparkthPlugin")

    plugin_name = _class_name_to_plugin_name(class_name)

    return plugin_name, plugin_class


def _class_name_to_plugin_name(class_name: str) -> str:
    """
    Convert class name to plugin name.

    Examples:
        CanvasPlugin -> canvas
        OpenEdxPlugin -> open-edx
    """
    if class_name.endswith("Plugin"):
        class_name = class_name[:-6]

    name = re.sub("([a-z0-9])([A-Z])", r"\1-\2", class_name)
    return name.lower()
