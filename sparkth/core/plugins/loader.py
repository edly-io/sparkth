"""
Plugin loader for Sparkth.

Manages plugin discovery and instantiation.
"""

import importlib
import inspect
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
    instantiated with no arguments (every plugin declares its own name by
    passing it positionally to ``super().__init__()``) and the resulting
    objects are stored in the loader instance keyed by that declared name.
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
        for plugin_class in self.iter_plugin_classes():
            try:
                plugin_instance = plugin_class()  # type: ignore[call-arg]
            except Exception as e:
                # We catch a broad exception here because we don't want failing plugins
                # to crash the app.
                logger.error(f"Failed to load plugin class '{plugin_class.__name__}'")
                logger.exception(e)
                continue

            try:
                plugin_name = plugin_instance.name
            except AttributeError as e:
                logger.error(
                    f"Plugin class '{plugin_class.__name__}' declares no name: "
                    "its __init__ must pass the plugin name to super().__init__()"
                )
                logger.exception(e)
                continue

            if plugin_name in self._loaded_plugins:
                existing_class = type(self._loaded_plugins[plugin_name]).__name__
                logger.error(
                    f"Duplicate plugin name '{plugin_name}': "
                    f"'{plugin_class.__name__}' clashes with already-loaded '{existing_class}'; skipping it"
                )
                continue

            self._loaded_plugins[plugin_name] = plugin_instance

    def iter_plugin_classes(self) -> Iterator[Type[SparkthPlugin]]:
        """
        Discover all plugin classes defined in get_plugin_settings().

        Yields:
            SparkthPlugin subclasses

        Note:
            All plugins are enabled by default.
            Format: "module.path:ClassName"
        """
        for module_string in get_plugin_settings():
            try:
                plugin_class = _load_plugin_class(module_string)
            except (PluginLoadError, PluginValidationError) as e:
                logger.warning(f"Failed to discover plugin from '{module_string}'")
                logger.exception(e)
                continue
            yield plugin_class

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


def _load_plugin_class(module_string: str) -> Type[SparkthPlugin]:
    """
    Load a plugin class from module string.

    Args:
        module_string: Module string in format "module.path:ClassName"

    Returns:
        The plugin class

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

    return plugin_class
