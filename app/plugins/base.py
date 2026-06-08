"""
SparkthPlugin Base Class

Provides the foundation for all Sparkth plugins. A plugin contributes its
capabilities to the relevant hooks from its ``__init__``:

- routes via ``ROUTES`` (``app.lib.routes.hooks``)
- MCP tools via ``MCP_TOOLS`` (``app.lib.mcp.hooks``)
- a config schema via ``CONFIG_SCHEMAS`` (``app.lib.config.hooks``)
"""


class SparkthPlugin:
    """
    Base class for Sparkth plugins.

    All plugins should inherit from this class. The loader constructs every plugin
    as ``plugin_class(plugin_name)``, so ``__init__`` must accept the derived
    ``plugin_name`` as its first positional argument and pass it through to
    ``super().__init__()``. Register routes, tools, and the config schema from
    within ``__init__``.

    Example:

    ```python
    from app.lib.mcp.hooks import MCP_TOOLS, Tool

    class MyAppPlugin(SparkthPlugin):
        def __init__(self, plugin_name: str) -> None:
            super().__init__(plugin_name)
            MCP_TOOLS.add_item(self, Tool(self.my_tool, category="utilities"))

        async def my_tool(self, payload: MyPayload) -> dict:
            \"\"\"Describe what the tool does (becomes the MCP tool description).\"\"\"
            ...
    ```
    """

    def __init__(self, name: str):
        """
        Initialize the plugin with its derived name.

        Args:
            name: Unique identifier for the plugin (e.g., "canvas")
        """
        self.name = name

    def __repr__(self) -> str:
        """Return string representation of the plugin."""
        return f"<SparkthPlugin: {self.name}>"
