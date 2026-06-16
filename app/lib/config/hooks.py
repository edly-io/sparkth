from app.lib.hooks import PluginHook
from app.lib.llm import LLMConfigAdapter
from app.lib.plugins import PluginConfig

# The Pydantic config class contributed by each plugin (one per plugin).
CONFIG_SCHEMAS: PluginHook[type[PluginConfig]] = PluginHook()

# The optional config adapter contributed by each plugin (one per plugin). The
# adapter preprocesses/postprocesses a plugin's stored config — e.g. validating a
# referenced LLMConfig belongs to the user. Consumed by PluginService.
CONFIG_ADAPTERS: PluginHook[LLMConfigAdapter] = PluginHook()
