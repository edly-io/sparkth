from app.lib.hooks import PluginHook
from app.plugins.config_base import PluginConfig

# The Pydantic config class contributed by each plugin (one per plugin).
CONFIG_SCHEMAS: PluginHook[type[PluginConfig]] = PluginHook()
