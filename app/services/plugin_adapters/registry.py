from app.core_plugins.chat.plugin_adapter import ChatPluginConfigAdapter
from app.services.plugin_adapters.base import PluginConfigAdapter

PLUGIN_ADAPTERS: dict[str, PluginConfigAdapter] = {
    "chat": ChatPluginConfigAdapter(),
}
