from app.lib.hooks import PluginHook
from app.lib.plugins import PluginConfig

# The Pydantic config class contributed by each plugin (one per plugin).
CONFIG_SCHEMAS: PluginHook[type[PluginConfig]] = PluginHook()
