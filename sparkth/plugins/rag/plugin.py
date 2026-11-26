from sparkth.lib.compose.hooks import register_agent
from sparkth.lib.plugins import SparkthPlugin
from sparkth.plugins.rag.agent import RAG


class RagPlugin(SparkthPlugin):
    """Finds the parts of the author's attached documents that Compose's steps need.

    It has no display info and no frontend, so the author never sees it as a plugin.
    """

    def __init__(self) -> None:
        super().__init__("rag")
        register_agent(self, RAG)
