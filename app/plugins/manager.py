from __future__ import annotations

from ..models import UserPlugin

"""
Plugin lifecycle management.

This module provides utilities for managing plugin configuration,
including which sparkth-plugins are enabled and their settings.
"""

import json
import os
from pathlib import Path
from typing import Any
from datetime import datetime
from sqlmodel import select
from app.models.plugin import UserPlugin


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


    def get_user_enabled_plugins(self, user_id: int, session) -> list[str]:
        """
        Get plugins enabled for a specific user.
        
        Logic:
        1. Get system-enabled plugins from config.json
        2. For each system-enabled plugin, check user preference
        3. If no user preference, default to enabled
        4. Return list of plugins enabled for this user
        
        :param user_id: User ID
        :param session: Database session
        :return: List of plugin names enabled for this user
        """
        from sqlmodel import select
        from app.models.plugin import UserPlugin
        
        system_enabled = self.get_enabled_plugins()
        
        # Get user preferences
        user_prefs = session.exec(
            select(UserPlugin).where(UserPlugin.user_id == user_id)
        ).all()
        
        user_pref_map = {pref.plugin_name: pref.enabled for pref in user_prefs}
        
        # Filter based on user preferences (default to enabled if no preference)
        user_enabled = []
        for plugin in system_enabled:
            if user_pref_map.get(plugin, True):
                user_enabled.append(plugin)
        
        return user_enabled
    
    def set_user_plugin_preference(
        self, user_id: int, plugin_name: str, enabled: bool, session
    ) -> "UserPlugin":
        """
        Set user's plugin preference.
        
        :param user_id: User ID
        :param plugin_name: Plugin name
        :param enabled: Whether to enable or disable
        :param session: Database session
        :return: UserPlugin instance
        :raises ValueError: If plugin is not system-enabled
        """

        
        # Check if plugin is system-enabled
        if plugin_name not in self.get_enabled_plugins():
            raise ValueError(f"Plugin '{plugin_name}' is not available system-wide")
        
        # Get or create preference
        pref = session.exec(
            select(UserPlugin).where(
                UserPlugin.user_id == user_id, UserPlugin.plugin_name == plugin_name
            )
        ).first()
        
        if pref:
            pref.enabled = enabled
            pref.updated_at = datetime.utcnow()
        else:
            pref = UserPlugin(user_id=user_id, plugin_name=plugin_name, enabled=enabled)
        
        session.add(pref)
        session.commit()
        session.refresh(pref)
        
        return pref
    
    def get_user_plugin_config(self, user_id: int, plugin_name: str, session) -> dict[str, Any]:
        """
        Get user's configuration for a specific plugin.
        
        :param user_id: User ID
        :param plugin_name: Plugin name
        :param session: Database session
        :return: Plugin configuration dict
        """
        from sqlmodel import select
        from app.models.plugin import UserPlugin
        
        pref = session.exec(
            select(UserPlugin).where(
                UserPlugin.user_id == user_id, UserPlugin.plugin_name == plugin_name
            )
        ).first()
        
        return pref.config if pref else {}
    
    def set_user_plugin_config(
        self, user_id: int, plugin_name: str, config: dict[str, Any], session
    ) -> "UserPlugin":
        """
        Set user's configuration for a specific plugin.
        
        :param user_id: User ID
        :param plugin_name: Plugin name
        :param config: Configuration dict
        :param session: Database session
        :return: User Plugin instance
        """
        from datetime import datetime
        from sqlmodel import select
        from app.models.plugin import UserPlugin
        
        # Get or create preference
        pref = session.exec(
            select(UserPlugin).where(
                UserPlugin.user_id == user_id, UserPlugin.plugin_name == plugin_name
            )
        ).first()
        
        if pref:
            pref.config = config
            pref.updated_at = datetime.utcnow()
        else:
            pref = UserPlugin(user_id=user_id, plugin_name=plugin_name, config=config)
        
        session.add(pref)
        session.commit()
        session.refresh(pref)
        
        return pref
    
    def get_user_plugin_preferences(self, user_id: int, session) -> dict[str, dict[str, Any]]:
        """
        Get all plugin preferences for a user.
        
        :param user_id: User ID
        :param session: Database session
        :return: Dict mapping plugin name to {enabled, config}
        """
        from sqlmodel import select
        from app.models.plugin import UserPlugin
        
        prefs = session.exec(select(UserPlugin).where(UserPlugin.user_id == user_id)).all()
        
        return {
            pref.plugin_name: {"enabled": pref.enabled, "config": pref.config} for pref in prefs
        }


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
