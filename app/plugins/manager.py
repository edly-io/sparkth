"""
Plugin Manager for Sparkth.

Manages plugin discovery, loading, and lifecycle based on configuration files.
"""

import importlib
import inspect
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from app.plugins.base import SparkthPlugin
from app.plugins.exceptions import (
    PluginAlreadyLoadedError,
    PluginDependencyError,
    PluginLoadError,
    PluginNotFoundError,
    PluginNotLoadedError,
    PluginValidationError,
)

logger = logging.getLogger(__name__)


class PluginManager:
    """
    Central manager for Sparkth plugins.
    
    Handles:
    - Configuration-based plugin discovery
    - Plugin loading and instantiation
    - Plugin lifecycle management (initialize, enable, disable)
    - Plugin dependency resolution
    - Runtime plugin state management
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        plugins_dir: Optional[Path] = None,
    ):
        """
        Initialize plugin manager.

        Args:
            config_path: Path to plugin configuration file (JSON).
                        Defaults to app/config/plugins.json
            plugins_dir: Base directory for plugin modules.
                        Defaults to app/plugins/
        """
        if config_path is None:
            # Default to app/config/plugins.json
            app_dir = Path(__file__).parent.parent
            config_path = app_dir / "config" / "plugins.json"

        if plugins_dir is None:
            # Default to app/plugins/
            app_dir = Path(__file__).parent.parent
            plugins_dir = app_dir / "plugins"

        self.config_path = config_path
        self.plugins_dir = plugins_dir
        self._config: Optional[Dict[str, Any]] = None
        
        # Store loaded plugin instances
        self._loaded_plugins: Dict[str, SparkthPlugin] = {}
        # Store available plugin classes (discovered from config)
        self._available_plugins: Dict[str, Type[SparkthPlugin]] = {}

    # ==================== Configuration Management ====================

    def load_config(self) -> Dict[str, Any]:
        """
        Load plugin configuration from file.

        Returns:
            Dictionary containing plugin configuration

        Raises:
            PluginLoadError: If config file cannot be loaded
        """
        if self._config is not None:
            return self._config

        if not self.config_path.exists():
            # Return empty config if file doesn't exist
            self._config = {"plugins": {}}
            return self._config

        try:
            with open(self.config_path, "r") as f:
                self._config = json.load(f)
        except json.JSONDecodeError as e:
            raise PluginLoadError(f"Invalid JSON in plugin config: {e}")
        except Exception as e:
            raise PluginLoadError(f"Failed to load plugin config: {e}")

        return self._config

    def reload_config(self) -> None:
        """
        Reload the plugin configuration from file.
        
        Useful for picking up configuration changes without restarting the app.
        """
        self._config = None
        self.load_config()

    def get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Plugin configuration dictionary
        """
        config = self.load_config()
        plugins_config = config.get("plugins", {})
        
        plugin_def = plugins_config.get(plugin_name, {})
        return plugin_def.get("config", {})

    def update_plugin_state(self, plugin_name: str, enabled: bool) -> None:
        """
        Update the enabled state of a plugin in the configuration file.

        Args:
            plugin_name: Name of the plugin
            enabled: Whether the plugin should be enabled

        Raises:
            PluginNotFoundError: If plugin is not in config
        """
        config = self.load_config()
        plugins_config = config.get("plugins", {})

        if plugin_name not in plugins_config:
            raise PluginNotFoundError(f"Plugin '{plugin_name}' not found in config")

        plugins_config[plugin_name]["enabled"] = enabled

        # Write back to file
        try:
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            raise PluginLoadError(f"Failed to update plugin config: {e}")

        # Reload config
        self._config = config

    # ==================== Plugin Discovery ====================

    def discover_plugins(self) -> Dict[str, Type[SparkthPlugin]]:
        """
        Discover all plugins defined in configuration.

        Returns:
            Dictionary mapping plugin names to plugin classes

        Example config structure:
            ```json
            {
              "plugins": {
                "tasks": {
                  "module": "app.plugins.tasks_plugin",
                  "class": "TasksPlugin",
                  "enabled": true,
                  "config": {
                    "max_tasks": 100
                  }
                }
              }
            }
            ```
        """
        config = self.load_config()
        plugins_config = config.get("plugins", {})
        
        discovered = {}

        for plugin_name, plugin_def in plugins_config.items():
            # Skip comment fields
            if plugin_name.startswith("_"):
                continue
                
            try:
                # Skip disabled plugins
                if not plugin_def.get("enabled", True):
                    continue

                plugin_class = self._load_plugin_class(plugin_name, plugin_def)
                if plugin_class:
                    discovered[plugin_name] = plugin_class

            except Exception as e:
                logger.warning(f"Failed to discover plugin '{plugin_name}': {e}")
                continue

        self._available_plugins = discovered
        return discovered

    def get_available_plugins(self) -> List[str]:
        """
        Get list of all available plugin names from configuration.

        Returns:
            List of all plugin names (enabled or disabled)
        """
        config = self.load_config()
        plugins_config = config.get("plugins", {})

        return [name for name in plugins_config.keys() if not name.startswith("_")]

    def get_enabled_plugins(self) -> List[str]:
        """
        Get list of enabled plugin names from configuration.

        Returns:
            List of plugin names that are enabled
        """
        config = self.load_config()
        plugins_config = config.get("plugins", {})

        enabled = []
        for plugin_name, plugin_def in plugins_config.items():
            if plugin_name.startswith("_"):
                continue
            if plugin_def.get("enabled", True):
                enabled.append(plugin_name)

        return enabled

    def is_plugin_enabled(self, plugin_name: str) -> bool:
        """
        Check if a plugin is enabled in configuration.

        Args:
            plugin_name: Name of the plugin

        Returns:
            True if plugin is enabled, False otherwise
        """
        config = self.load_config()
        plugins_config = config.get("plugins", {})
        
        if plugin_name not in plugins_config:
            return False
        
        return plugins_config[plugin_name].get("enabled", True)

    def _load_plugin_class(
        self,
        plugin_name: str,
        plugin_def: Dict[str, Any]
    ) -> Optional[Type[SparkthPlugin]]:
        """
        Load a plugin class from its definition.

        Args:
            plugin_name: Name of the plugin
            plugin_def: Plugin definition from config

        Returns:
            Plugin class or None if loading fails

        Raises:
            PluginLoadError: If plugin cannot be loaded
            PluginValidationError: If plugin is invalid
        """
        # Get module and class name from config
        module_name = plugin_def.get("module")
        class_name = plugin_def.get("class")

        if not module_name or not class_name:
            raise PluginLoadError(
                f"Plugin '{plugin_name}' missing 'module' or 'class' in config"
            )

        try:
            # Import the module
            module = importlib.import_module(module_name)
        except ImportError as e:
            raise PluginLoadError(
                f"Failed to import module '{module_name}' for plugin '{plugin_name}': {e}"
            )

        # Get the class from the module
        if not hasattr(module, class_name):
            raise PluginLoadError(
                f"Class '{class_name}' not found in module '{module_name}'"
            )

        plugin_class = getattr(module, class_name)

        # Validate that it's a SparkthPlugin subclass
        if not (inspect.isclass(plugin_class) and issubclass(plugin_class, SparkthPlugin)):
            raise PluginValidationError(
                f"Class '{class_name}' must be a subclass of SparkthPlugin"
            )

        return plugin_class

    # ==================== Plugin Loading & Lifecycle ====================

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

        # Discover if not already done
        if not self._available_plugins:
            self.discover_plugins()

        # Check if plugin is available
        if plugin_name not in self._available_plugins:
            raise PluginNotFoundError(f"Plugin '{plugin_name}' not found in config")

        plugin_class = self._available_plugins[plugin_name]
        plugin_config = self.get_plugin_config(plugin_name)

        try:
            # Instantiate the plugin
            plugin_instance = plugin_class()
            
            # Set plugin configuration
            if plugin_config:
                plugin_instance.update_config(plugin_config)
            
            # Initialize the plugin
            plugin_instance.initialize()
            
            # Store the instance
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
        
        # Disable if currently enabled
        if plugin.is_enabled():
            plugin.disable()
        
        # Remove from loaded plugins
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

    # ==================== Batch Operations ====================

    def load_all_enabled(self) -> Dict[str, SparkthPlugin]:
        """
        Load all enabled plugins from configuration.

        Returns:
            Dictionary of successfully loaded plugins

        Note:
            Continues loading other plugins if one fails.
            Check logs for any failures.
        """
        enabled_plugins = self.get_enabled_plugins()
        loaded = {}

        for plugin_name in enabled_plugins:
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

    # ==================== Plugin Information ====================

    def get_plugin_info(self, plugin_name: str) -> Dict[str, Any]:
        """
        Get comprehensive information about a plugin.

        Args:
            plugin_name: Name of the plugin

        Returns:
            Dictionary containing plugin information
        """
        info = {
            "name": plugin_name,
            "loaded": self.is_plugin_loaded(plugin_name),
            "enabled_in_config": self.is_plugin_enabled(plugin_name),
            "config": self.get_plugin_config(plugin_name),
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
