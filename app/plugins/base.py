"""
SparkthPlugin Base Class

Provides the foundation for all Sparkth plugins with support for:
- Route registration
- Database models and migrations
- MCP tools
- Dependencies
- Configuration management
- Lifecycle hooks
"""

from typing import Any, Callable, Type, TypeVar

from app.lib.log import get_logger
from app.plugins.config_base import PluginConfig

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def tool(
    name: str | None = None,
    description: str = "",
    category: str | None = None,
    version: str = "1.0.0",
) -> Callable[[F], F]:
    """
        Decorator to mark a method as an MCP tool in a plugin.

        This decorator marks methods for registration as MCP tools.
        The actual registration happens automatically when the plugin is instantiated.

        Args:
            name: Tool name (uses method name if not provided)
            description: Tool description (uses docstring if not provided)
            category: Tool category (e.g., "database", "api", "utilities")
            version: Tool version

        Returns:
            Decorator function

        Example:
    ```python
            from app.plugins.base import SparkthPlugin, tool

            class CanvasPlugin(SparkthPlugin):
                @tool(description="Authenticate Canvas API", category="auth")
                async def canvas_authenticate(self, auth: AuthPayload) -> dict:
                    return await CanvasClient.authenticate(auth.api_url, auth.api_token)

                @tool(description="Get courses", category="courses")
                async def canvas_get_courses(self, auth: AuthPayload, page: int) -> dict:
                    async with CanvasClient(auth.api_url, auth.api_token) as client:
                        return await client.get(f"courses?page={page}")
    ```
    """

    def decorator(func: F) -> F:
        setattr(func, "_is_mcp_tool", True)
        setattr(func, "_mcp_tool_name", name if name else func.__name__)
        setattr(func, "_mcp_tool_description", description or (func.__doc__ or "").strip())
        setattr(func, "_mcp_tool_category", category)
        setattr(func, "_mcp_tool_version", version)
        return func

    return decorator


class PluginMeta(type):
    """
    Metaclass for SparkthPlugin that automatically collects @tool decorated methods.

    This metaclass scans the class definition for methods marked with the @tool
    decorator and stores them in a class-level registry. When the plugin is
    instantiated, these tools are automatically registered.
    """

    _tool_registry: dict[str, dict[str, Any]]

    def __new__(
        mcs: Type["PluginMeta"], name: str, bases: tuple[Type[Any], ...], namespace: dict[str, Any]
    ) -> "PluginMeta":
        cls = super().__new__(mcs, name, bases, namespace)

        cls._tool_registry = {}

        for attr_name, attr_value in namespace.items():
            if callable(attr_value) and getattr(attr_value, "_is_mcp_tool", False):
                cls._tool_registry[attr_name] = {
                    "name": getattr(attr_value, "_mcp_tool_name", attr_name),
                    "description": getattr(attr_value, "_mcp_tool_description", ""),
                    "category": getattr(attr_value, "_mcp_tool_category", None),
                    "version": getattr(attr_value, "_mcp_tool_version", "1.0.0"),
                }
                logger.debug(f"Collected tool '{getattr(attr_value, '_mcp_tool_name', attr_name)}' from class '{name}'")

        return cls


class SparkthPlugin(metaclass=PluginMeta):
    """
        Base class for Sparkth plugins.

        All plugins should inherit from this class and override the relevant methods
        to add custom functionality. Unlike abstract base classes, this provides
        default implementations for all methods, making it easy to create simple
        plugins that only override what they need.

        The manager constructs every plugin as ``plugin_class(plugin_name)``,
        so ``__init__`` must accept the derived ``plugin_name`` as its first
        positional argument and pass it through to ``super().__init__()``.
        Register routes, models, and tools from within ``__init__``.

        Example:
    ```python
            router = APIRouter(prefix="/my-app")

            @router.get("/")
            def my_endpoint():
                return {"message": "Hello from plugin!"}

            class MyAppPlugin(SparkthPlugin):
                def __init__(self, plugin_name: str) -> None:
                    super().__init__(
                        plugin_name,
                        MyAppPluginConfig,
                        version="1.0.0",
                        description="My awesome plugin",
                        author="Your Name",
                    )
                    self.add_route(router)
    ```
    """

    _tool_registry: dict[str, dict[str, Any]]

    def __init__(
        self,
        name: str,
        config_schema: Type[PluginConfig] | None = None,
        is_core: bool = False,
        version: str = "1.0.0",
        description: str = "",
        author: str = "",
    ):
        """
        Initialize the plugin with metadata.

        Args:
            name: Unique identifier for the plugin (e.g., "tasks-plugin")
            config_schema: Plugin-specific configuration (inherits from app.plugins.config_base:PluginConfig)
            version: Semantic version string (e.g., "1.0.0")
            description: Brief description of plugin functionality
            author: Plugin author name or organization
        """
        self.name = name
        self.version = version
        self.description = description
        self.is_core = is_core
        self.author = author
        self.config_schema = config_schema

        # Collect @tool-decorated methods into the MCP_TOOLS hook. Imported lazily
        # to avoid an import cycle (the hook module imports SparkthPlugin).
        from app.lib.mcp.hooks import collect_plugin_tools

        collect_plugin_tools(self)

    def get_config_schema(self) -> dict[str, Any]:
        """
        Return JSON Schema for plugin configuration validation.

        Uses the plugin's Pydantic model to generate the schema.

        Returns:
            JSON Schema dictionary
        """
        return self.config_schema.model_json_schema() if self.config_schema else {}

    def __repr__(self) -> str:
        """Return string representation of the plugin."""
        return f"<SparkthPlugin: {self.name} v{self.version}>"
