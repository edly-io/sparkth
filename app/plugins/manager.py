"""
Plugin Manager for Sparkth.

Manages plugin discovery, loading, and lifecycle based on configuration.
"""

import importlib
import inspect
import re
from typing import Any, Dict, List, Type

from app.core.config import get_plugin_settings
from app.core.logger import get_logger
from app.plugins.base import SparkthPlugin
from app.plugins.exceptions import (
    PluginAlreadyLoadedError,
    PluginLoadError,
    PluginNotFoundError,
    PluginNotLoadedError,
    PluginValidationError,
)

logger = get_logger(__name__)


class PluginManager:
    """
    Central manager for Sparkth plugins.

    Handles:
    - Plugin discovery from core configuration
    - Plugin loading and instantiation
    - Plugin lifecycle management (initialize, enable, disable)
    - Runtime plugin state management
    """

    def __init__(self) -> None:
        """Initialize plugin manager."""
        self._loaded_plugins: Dict[str, SparkthPlugin] = {}
        self._available_plugins: Dict[str, Type[SparkthPlugin]] = {}

    def discover_plugins(self) -> Dict[str, Type[SparkthPlugin]]:
        """
        Discover all plugins defined in get_plugin_settings().

        Returns:
            Dictionary mapping plugin names to plugin classes

        Note:
            All plugins are enabled by default.
            Format: "module.path:ClassName"
        """
        discovered: Dict[str, Type[SparkthPlugin]] = {}

        for module_string in get_plugin_settings():
            try:
                plugin_name, plugin_class = self._load_plugin_class(module_string)
                if plugin_class:
                    discovered[plugin_name] = plugin_class
            except Exception as e:
                logger.warning(f"Failed to discover plugin from '{module_string}': {e}")
                continue

        self._available_plugins = discovered
        return discovered

    def get_available_plugins(self) -> List[str]:
        """
        Get list of all available plugin names.

        Returns:
            List of all plugin names
        """
        if not self._available_plugins:
            self.discover_plugins()
        return list(self._available_plugins.keys())

    def _load_plugin_class(self, module_string: str) -> tuple[str, Type[SparkthPlugin]]:
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
            Example: "app.core_plugins.canvas.plugin:CanvasPlugin"
        """
        if ":" not in module_string:
            raise PluginLoadError(f"Invalid module format. Expected 'module.path:ClassName', got '{module_string}'")

        try:
            module_name, class_name = module_string.split(":", 1)
        except ValueError:
            raise PluginLoadError(f"Invalid module format. Expected 'module.path:ClassName', got '{module_string}'")

        module_name = module_name.strip()
        class_name = class_name.strip()

        if not module_name or not class_name:
            raise PluginLoadError(f"Empty module or class name in '{module_string}'")

        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            raise PluginLoadError(f"Failed to import module '{module_name}': {e}")

        if not hasattr(module, class_name):
            raise PluginLoadError(f"Class '{class_name}' not found in module '{module_name}'")

        plugin_class = getattr(module, class_name)

        if not (inspect.isclass(plugin_class) and issubclass(plugin_class, SparkthPlugin)):
            raise PluginValidationError(f"Class '{class_name}' must be a subclass of SparkthPlugin")

        plugin_name = self._class_name_to_plugin_name(class_name)

        return plugin_name, plugin_class

    def _class_name_to_plugin_name(self, class_name: str) -> str:
        """
        Convert class name to plugin name.

        Examples:
            CanvasPlugin -> canvas-plugin
            OpenEdXPlugin -> openedx-plugin
        """
        if class_name.endswith("Plugin"):
            class_name = class_name[:-6]

        name = re.sub("([a-z0-9])([A-Z])", r"\1-\2", class_name)
        return name.lower()

    def load_plugin(self, plugin_name: str) -> SparkthPlugin:
        """
        Load and instantiate a plugin.

        Args:
            plugin_name: Name of the plugin to load

        Returns:
            Loaded plugin instance

        Raises:
            PluginAlreadyLoadedError: If plugin is already loaded
            PluginNotFoundError: If plugin is not in config
            PluginLoadError: If plugin fails to load
        """
        if plugin_name in self._loaded_plugins:
            raise PluginAlreadyLoadedError(f"Plugin '{plugin_name}' is already loaded")

        if not self._available_plugins:
            self.discover_plugins()

        if plugin_name not in self._available_plugins:
            raise PluginNotFoundError(f"Plugin '{plugin_name}' not found in config")

        plugin_class = self._available_plugins[plugin_name]

        try:
            plugin_instance = plugin_class(plugin_name)

            plugin_instance.initialize()

            self._loaded_plugins[plugin_name] = plugin_instance

            return plugin_instance

        except Exception as e:
            raise PluginLoadError(f"Failed to load plugin '{plugin_name}': {e}")

    def unload_plugin(self, plugin_name: str) -> None:
        """
               Unload a plugin.

               Args:
                   plugin_name: Name of the plugin to unload

        Raises:
            PluginNotLoadedError: If plugin is not currently loaded
        """
        if plugin_name not in self._loaded_plugins:
            raise PluginNotLoadedError(f"Plugin '{plugin_name}' is not loaded")

        plugin = self._loaded_plugins[plugin_name]

        if plugin.is_enabled():
            plugin.disable()

        del self._loaded_plugins[plugin_name]

    def enable_plugin(self, plugin_name: str) -> None:
        """
        Enable a loaded plugin.

        Args:
            plugin_name: Name of the plugin to enable

        Raises:
            PluginNotLoadedError: If plugin is not loaded
        """
        if plugin_name not in self._loaded_plugins:
            raise PluginNotLoadedError(f"Plugin '{plugin_name}' is not loaded")

        plugin = self._loaded_plugins[plugin_name]
        plugin.enable()

    def disable_plugin(self, plugin_name: str) -> None:
        """
        Disable a loaded plugin.

        Args:
            plugin_name: Name of the plugin to disable

        Raises:
            PluginNotLoadedError: If plugin is not loaded
        """
        if plugin_name not in self._loaded_plugins:
            raise PluginNotLoadedError(f"Plugin '{plugin_name}' is not loaded")

        plugin = self._loaded_plugins[plugin_name]
        plugin.disable()

    def get_plugin(self, plugin_name: str) -> SparkthPlugin:
        """
        Get a loaded plugin instance.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin instance

        Raises:
            PluginNotLoadedError: If plugin is not loaded
        """
        if plugin_name not in self._loaded_plugins:
            raise PluginNotLoadedError(f"Plugin '{plugin_name}' is not loaded")

        return self._loaded_plugins[plugin_name]

    def get_loaded_plugins(self) -> Dict[str, SparkthPlugin]:
        """
        Get all loaded plugin instances.

        Returns:
            Dictionary mapping plugin names to plugin instances
        """
        return self._loaded_plugins.copy()

    def is_plugin_loaded(self, plugin_name: str) -> bool:
        """
        Check if a plugin is currently loaded.

        Args:
            plugin_name: Name of the plugin

        Returns:
            True if plugin is loaded, False otherwise
        """
        return plugin_name in self._loaded_plugins

    def load_all_enabled(self) -> Dict[str, SparkthPlugin]:
        """
        Load all plugins from configuration.
        All plugins in get_plugin_settings() are enabled by default.

        Returns:
            Dictionary of successfully loaded plugins

        Note:
            Continues loading other plugins if one fails.
            Check logs for any failures.
        """
        available_plugins = self.get_available_plugins()
        loaded: Dict[str, SparkthPlugin] = {}

        for plugin_name in available_plugins:
            try:
                plugin = self.load_plugin(plugin_name)
                loaded[plugin_name] = plugin
            except Exception as e:
                logger.error(f"Failed to load plugin '{plugin_name}': {e}")
                continue

        return loaded

    def enable_all_loaded(self) -> None:
        """Enable all currently loaded plugins."""
        for plugin_name in self._loaded_plugins:
            try:
                self.enable_plugin(plugin_name)
            except Exception as e:
                logger.error(f"Failed to enable plugin '{plugin_name}': {e}")
                continue

    def disable_all_loaded(self) -> None:
        """Disable all currently loaded plugins."""
        for plugin_name in self._loaded_plugins:
            try:
                self.disable_plugin(plugin_name)
            except Exception as e:
                logger.error(f"Failed to disable plugin '{plugin_name}': {e}")
                continue

    def unload_all(self) -> None:
        """Unload all currently loaded plugins."""
        plugin_names = list(self._loaded_plugins.keys())
        for plugin_name in plugin_names:
            try:
                self.unload_plugin(plugin_name)
            except Exception as e:
                logger.error(f"Failed to unload plugin '{plugin_name}': {e}")
                continue

    def get_plugin_info(self, plugin_name: str) -> Dict[str, Any]:
        """
        Get comprehensive information about a plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Dictionary containing plugin information
        """
        info: Dict[str, Any] = {
            "name": plugin_name,
            "loaded": self.is_plugin_loaded(plugin_name),
            "enabled": True,
        }

        if self.is_plugin_loaded(plugin_name):
            plugin = self.get_plugin(plugin_name)
            info.update(plugin.get_info())

        return info

    def list_all_plugins(self) -> List[Dict[str, Any]]:
        """
        Get information about all available plugins.

        Returns:
            List of plugin information dictionaries
        """
        all_plugins = self.get_available_plugins()
        return [self.get_plugin_info(name) for name in all_plugins]
