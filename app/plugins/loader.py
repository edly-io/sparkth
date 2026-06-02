"""
Plugin Manager for Sparkth.

Manages plugin discovery, loading, and lifecycle based on configuration.
"""

import importlib
import inspect
import re
from typing import Iterator, Type

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_plugin_settings
from app.core.db import async_engine
from app.lib.log import get_logger
from app.plugins.base import SparkthPlugin
from app.plugins.exceptions import (
    PluginAlreadyLoadedError,
    PluginLoadError,
    PluginNotFoundError,
    PluginValidationError,
)

logger = get_logger(__name__)


class PluginLoader:
    """
    Central loader for Sparkth plugins.

    Handles:
    - Plugin discovery from core configuration
    - Plugin loading and instantiation
    - Plugin lifecycle management (initialize, enable, disable)
    - Runtime plugin state management
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
        """Initialize plugin manager."""
        self._loaded_plugins: dict[str, SparkthPlugin] = {}

    async def load_all(self) -> None:
        """
        Load all plugins from configuration.
        All plugins in get_plugin_settings() are enabled by default.

        Returns:
            Dictionary of successfully loaded plugins

        Note:
            Continues loading other plugins if one fails.
            Check logs for any failures.
        """
        for plugin_name, plugin_class in self.iter_plugin_classes():
            try:
                plugin_instance = plugin_class(plugin_name)
                await self._load_plugin(plugin_instance)
            except (PluginLoadError, PluginNotFoundError, PluginAlreadyLoadedError) as e:
                logger.error(f"Failed to load plugin '{plugin_name}'")
                logger.exception(e)
                continue

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

    async def _load_plugin(self, plugin_instance: SparkthPlugin) -> None:
        """
        Load and instantiate a plugin.

        Args:
            plugin_name: Name of the plugin to load

        Returns:
            Loaded plugin instance

        Raises:
            PluginLoadError: If plugin fails to load
        """
        # TODO this is a lazy import to avoid circular dependencies. We should be able
        # to get rid of it once we get rid of PLUGIN_CONFIG_CLASSES.
        from app.services.plugin import PluginService

        try:
            self._loaded_plugins[plugin_instance.name] = plugin_instance
            plugin_service = PluginService()

            async with AsyncSession(async_engine, expire_on_commit=False) as session:
                await plugin_service.get_or_create(
                    session,
                    plugin_instance.name,
                    plugin_instance.is_core,
                    plugin_instance.get_config_schema(),
                )

        except (TypeError, AttributeError, RuntimeError) as e:
            raise PluginLoadError(f"Failed to load plugin {plugin_instance.name}") from e

    def get_loaded_plugins(self) -> list[tuple[str, SparkthPlugin]]:
        """
        Get all loaded plugin instances. Note that load_all() must be called before.

        Returns:
            Dictionary mapping plugin names to plugin instances
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
