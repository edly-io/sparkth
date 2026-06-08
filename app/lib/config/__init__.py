from collections.abc import Iterator

from app.lib.config.hooks import CONFIG_SCHEMAS
from app.plugins.config_base import PluginConfig


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
