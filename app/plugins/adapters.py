from app.core_plugins.chat.adapter import ChatConfigAdapter
from app.core_plugins.slack.adapter import SlackConfigAdapter
from app.llm.adapter import LLMConfigAdapter

PLUGIN_ADAPTERS: dict[str, LLMConfigAdapter] = {
    "chat": ChatConfigAdapter(),
    "slack": SlackConfigAdapter(),
}
