from collections.abc import Iterator

from app.lib.hooks import PluginHook
from app.plugins.config_base import PluginConfig

# The Pydantic config class contributed by each plugin (one per plugin).
CONFIG_SCHEMAS: PluginHook[type[PluginConfig]] = PluginHook()


def iter_plugin_config_schemas() -> Iterator[tuple[str, type[PluginConfig]]]:
    """Yield (plugin_name, config_class) for every plugin that contributed a config."""
    # Ensure plugins are instantiated so CONFIG_SCHEMAS is populated.
    from app.plugins import get_plugin_loader

    get_plugin_loader()
    for plugin, config_schema in CONFIG_SCHEMAS.iter_items():
        yield plugin.name, config_schema


def get_plugin_config_schema(plugin_name: str) -> type[PluginConfig] | None:
    """Return the config class a plugin contributed, looked up by plugin name."""
    for name, config_schema in iter_plugin_config_schemas():
        if name == plugin_name:
            return config_schema
    return None
