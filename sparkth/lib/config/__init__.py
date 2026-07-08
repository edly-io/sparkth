from collections.abc import Iterator

from sparkth.lib.config.hooks import CONFIG_ADAPTERS, CONFIG_SCHEMAS
from sparkth.lib.llm import LLMConfigAdapter
from sparkth.lib.plugins import PluginConfig


def iter_plugin_config_schemas() -> Iterator[tuple[str, type[PluginConfig]]]:
    """Yield (plugin_name, config_class) for every plugin that contributed a config.

    Plugins are instantiated once per process at the entrypoint (the FastAPI
    lifespan, the standalone MCP server, or the migration runner), which is what
    populates CONFIG_SCHEMAS; this iterator assumes that has already happened.
    """
    for plugin, config_schema in CONFIG_SCHEMAS.iter_items():
        yield plugin.name, config_schema


def get_plugin_config_schema(plugin_name: str) -> type[PluginConfig] | None:
    """Return the config class a plugin contributed, looked up by plugin name."""
    for name, config_schema in iter_plugin_config_schemas():
        if name == plugin_name:
            return config_schema
    return None


def iter_plugin_adapters() -> Iterator[tuple[str, LLMConfigAdapter]]:
    """Yield (plugin_name, adapter) for every plugin that contributed a config adapter.

    Like CONFIG_SCHEMAS, CONFIG_ADAPTERS is populated when plugins are instantiated
    at the process entrypoint; this iterator assumes that has already happened.
    """
    for plugin, adapter in CONFIG_ADAPTERS.iter_items():
        yield plugin.name, adapter


def get_plugin_adapter(plugin_name: str) -> LLMConfigAdapter | None:
    """Return the config adapter a plugin contributed, looked up by plugin name."""
    for name, adapter in iter_plugin_adapters():
        if name == plugin_name:
            return adapter
    return None
