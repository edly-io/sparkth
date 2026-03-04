from app.core_plugins.chat.plugin_adapter import ChatPluginConfigAdapter

PLUGIN_ADAPTERS: dict[str, ChatPluginConfigAdapter] = {
    "chat": ChatPluginConfigAdapter(),
}
