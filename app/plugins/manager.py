from __future__ import annotations
"""
Plugin lifecycle management.

This module provides utilities for managing plugin configuration,
including which sparkth-plugins are enabled and their settings.
"""

import json
import os
from pathlib import Path
from typing import Any

from .base import DEFAULT_PLUGINS_ROOT


class PluginManager:
    """
    Manager for plugin configuration and lifecycle.

    This class handles loading and saving plugin configuration,
    including which sparkth-plugins are enabled and their settings.
    """

    def __init__(self, config_path: str | None = None):
        """
        Initialize the plugin manager.

        :param config_path: Path to the configuration file. If None, uses default.
        """
        if config_path is None:
            config_dir = os.path.join(os.path.expanduser("~"), ".sparkth")
            config_path = os.path.join(config_dir, "config.json")

        self.config_path = config_path
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Ensure the configuration directory exists."""
        config_dir = os.path.dirname(self.config_path)
        Path(config_dir).mkdir(parents=True, exist_ok=True)

    def load_config(self) -> dict[str, Any]:
        """
        Load the configuration file.

        :return: Configuration dictionary
        """
        if not os.path.exists(self.config_path):
            return {}

        with open(self.config_path, "r") as f:
            config = json.load(f)

        return config

    def save_config(self, config: dict[str, Any]) -> None:
        """
        Save the configuration file.

        :param config: Configuration dictionary to save
        """
        self._ensure_config_dir()

        with open(self.config_path, "w") as f:
            json.dump(config, f, indent=2)

    def get_enabled_plugins(self) -> list[str]:
        """
        Get the list of enabled sparkth-plugins.

        :return: List of enabled plugin names
        """
        config = self.load_config()
        return config.get("sparkth-plugins", {}).get("enabled", [])

    def set_enabled_plugins(self, plugins: list[str]) -> None:
        """
        Set the list of enabled sparkth-plugins.

        :param plugins: List of plugin names to enable
        """
        config = self.load_config()

        if "sparkth-plugins" not in config:
            config["sparkth-plugins"] = {}

        config["sparkth-plugins"]["enabled"] = plugins
        self.save_config(config)

    def enable_plugin(self, name: str) -> None:
        """
        Enable a plugin.

        :param name: Name of the plugin to enable
        """
        enabled = self.get_enabled_plugins()
        if name not in enabled:
            enabled.append(name)
            self.set_enabled_plugins(enabled)

    def disable_plugin(self, name: str) -> None:
        """
        Disable a plugin.

        :param name: Name of the plugin to disable
        """
        enabled = self.get_enabled_plugins()
        if name in enabled:
            enabled.remove(name)
            self.set_enabled_plugins(enabled)

    def is_enabled(self, name: str) -> bool:
        """
        Check if a plugin is enabled.

        :param name: Name of the plugin to check
        :return: True if the plugin is enabled, False otherwise
        """
        return name in self.get_enabled_plugins()

    def get_plugin_config(self, plugin_name: str) -> dict[str, Any]:
        """
        Get the configuration for a specific plugin.

        :param plugin_name: Name of the plugin
        :return: Plugin configuration dictionary
        """
        config = self.load_config()
        return config.get("sparkth-plugins", {}).get("config", {}).get(plugin_name, {})

    def set_plugin_config(self, plugin_name: str, plugin_config: dict[str, Any]) -> None:
        """
        Set the configuration for a specific plugin.

        :param plugin_name: Name of the plugin
        :param plugin_config: Configuration dictionary for the plugin
        """
        config = self.load_config()

        if "sparkth-plugins" not in config:
            config["sparkth-plugins"] = {}
        if "config" not in config["sparkth-plugins"]:
            config["sparkth-plugins"]["config"] = {}

        config["sparkth-plugins"]["config"][plugin_name] = plugin_config
        self.save_config(config)


# Global plugin manager instance
_manager: PluginManager | None = None


def get_manager() -> PluginManager:
    """
    Get the global plugin manager instance.

    :return: The global PluginManager instance
    """
    global _manager
    if _manager is None:
        _manager = PluginManager()
    return _manager
