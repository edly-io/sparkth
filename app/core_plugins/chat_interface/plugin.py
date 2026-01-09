from app.plugins.base import SparkthPlugin


class ChatInterface(SparkthPlugin):
    """
    Chat Interface Integration Plugin
    """

    def __init__(self, plugin_name: str) -> None:
        super().__init__(
            plugin_name,
            is_core=True,
            version="1.0.0",
            description="Chat interface integration plugin",
            author="Sparkth Team",
        )
