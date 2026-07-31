"""
SparkthPlugin Base Class

Provides the foundation for all Sparkth plugins. A plugin contributes its
capabilities to the relevant hooks from its ``__init__``:

- routes via ``register_router`` (``sparkth.lib.routes``)
- MCP tools via ``MCP_TOOLS`` (``sparkth.lib.mcp.hooks``)
- a config schema via ``CONFIG_SCHEMAS`` (``sparkth.lib.config.hooks``)
- frontend metadata via ``DISPLAY_INFO`` / ``SIDEBAR_ENTRIES`` / ``FRONTEND_APPS``
  (``sparkth.lib.frontend.hooks``)
"""

import re

# A plugin name is a kebab-case slug: it appears in URLs (``/api/v1/<name>``,
# ``/dashboard/<name>``) and is the key joining the backend plugin, its DB row,
# and its frontend counterpart.
PLUGIN_NAME_PATTERN = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


class SparkthPlugin:
    """
    Base class for Sparkth plugins.

    All plugins should inherit from this class. Each plugin declares its own
    name explicitly by passing it positionally to ``super().__init__()``; the
    loader constructs every plugin as ``plugin_class()`` and reads the declared
    name; nothing is ever derived from the class name. Register routes, tools,
    the config schema, and frontend metadata from within ``__init__``.

    Example:

    ```python
    from sparkth.lib.mcp.hooks import MCP_TOOLS, Tool

    class MyAppPlugin(SparkthPlugin):
        def __init__(self) -> None:
            super().__init__("my-app")
            MCP_TOOLS.add_item(self, Tool(self.my_tool, category="utilities"))

    async def my_tool(self, payload: MyPayload) -> dict:
        \"\"\"Describe what the tool does (becomes the MCP tool description).\"\"\"
        ...
    ```
    """

    def __init__(self, name: str):
        """
        Initialize the plugin with its declared name.

        Args:
            name: Unique identifier for the plugin (e.g., "canvas"). Must be a
                kebab-case slug (lowercase letters, digits, single hyphens).

        Raises:
            ValueError: If the name is not a valid kebab-case slug.
        """
        if not PLUGIN_NAME_PATTERN.fullmatch(name):
            raise ValueError(
                f"Invalid plugin name {name!r}: must be a kebab-case slug (lowercase letters, digits, hyphens)"
            )
        self.name = name

    def __repr__(self) -> str:
        """Return string representation of the plugin."""
        return f"<SparkthPlugin: {self.name}>"
