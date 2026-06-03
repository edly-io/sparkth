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

import inspect
from typing import Any, Callable, Type, TypeVar, get_type_hints

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
        self._mcp_tools: list[dict[str, Any]] = []

        self._register_tools_from_metaclass()

    def _register_tools_from_metaclass(self) -> None:
        """
        Register all tools that were collected by the PluginMeta metaclass.

        This method is called automatically during __init__ and registers all
        methods that were decorated with @tool at class definition time.
        """
        tool_registry = getattr(self.__class__, "_tool_registry", {})

        for method_name, tool_info in tool_registry.items():
            try:
                bound_method = getattr(self, method_name)
                self.add_mcp_tool(
                    name=tool_info["name"],
                    handler=bound_method,
                    description=tool_info["description"],
                    category=tool_info["category"],
                    version=tool_info["version"],
                )
                logger.debug(
                    f"Auto-registered tool '{tool_info['name']}' from method '{method_name}' in plugin '{self.name}'"
                )
            except (AttributeError, TypeError, KeyError) as e:
                logger.error(f"Failed to auto-register tool from method '{method_name}' in plugin '{self.name}': {e}")

    def add_mcp_tool(
        self,
        name: str,
        handler: Callable[..., Any],
        description: str = "",
        input_schema: dict[str, Any] | None = None,
        category: str | None = None,
        version: str = "1.0.0",
    ) -> None:
        """
                Add an MCP tool to this plugin.

                Args:
                    name: Tool name
                    handler: Callable that handles the tool invocation
                    description: Tool description
                    input_schema: JSON Schema for tool input parameters (auto-generated if not provided)
                    category: Tool category (e.g., "database", "api", "utilities")
                    version: Tool version

                Note:
                    Most plugins should prefer the ``@tool`` decorator on a method
                    instead — decorated methods are collected and registered
                    automatically. Use ``add_mcp_tool`` for dynamically built tools.

                Example:
        ```python
                    class TasksPlugin(SparkthPlugin):
                        def __init__(self, plugin_name: str) -> None:
                            super().__init__(plugin_name)

                            async def create_task_handler(title: str) -> str:
                                return f"Created task: {title}"

                            self.add_mcp_tool(
                                name="create_task",
                                handler=create_task_handler,
                                description="Create a new task",
                                category="tasks",
                                version="1.0.0",
                            )
        ```
        """
        if input_schema is None:
            input_schema = self._generate_input_schema(handler)

        tool_def = {
            "name": name,
            "handler": handler,
            "description": description,
            "inputSchema": input_schema,
            "category": category,
            "version": version,
            "plugin": self.name,
        }
        self._mcp_tools.append(tool_def)

    def _generate_input_schema(self, func: Callable[..., Any]) -> dict[str, Any]:
        """
        Auto-generate JSON Schema from function signature using type hints.

        Args:
            func: Function to generate schema for

        Returns:
            JSON Schema dictionary for the function's parameters
        """
        try:
            sig = inspect.signature(func)
            type_hints = get_type_hints(func)

            properties: dict[str, Any] = {}
            required: list[str] = []

            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                param_type = type_hints.get(param_name, str)
                properties[param_name] = self._type_to_json_schema(param_type)

                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            schema: dict[str, Any] = {"type": "object", "properties": properties}
            if required:
                schema["required"] = required
            return schema

        except (TypeError, NameError, AttributeError) as e:
            logger.warning(f"Failed to generate input schema for {func.__name__}: {e}. Using empty schema.")
            return {"type": "object", "properties": {}}

    def _type_to_json_schema(self, py_type: Type[Any]) -> dict[str, Any]:
        """
        Convert Python type to JSON Schema type definition.

        Args:
            py_type: Python type to convert

        Returns:
            JSON Schema type definition
        """
        # Check if it's a Pydantic BaseModel
        try:
            from pydantic import BaseModel

            if isinstance(py_type, type) and issubclass(py_type, BaseModel):
                model_schema = py_type.model_json_schema()
                defs = model_schema.get("$defs", {})
                properties = model_schema.get("properties", {})
                # Resolve all $ref references inline so the schema is self-contained
                resolved_properties = {k: self._resolve_schema_refs(v, defs) for k, v in properties.items()}
                return {
                    "type": "object",
                    "properties": resolved_properties,
                    "required": model_schema.get("required", []),
                }
        except (ImportError, TypeError):
            pass

        type_map: dict[Type[Any], dict[str, str]] = {
            int: {"type": "integer"},
            float: {"type": "number"},
            str: {"type": "string"},
            bool: {"type": "boolean"},
            list: {"type": "array"},
            dict: {"type": "object"},
        }

        if py_type in type_map:
            return type_map[py_type]

        origin = getattr(py_type, "__origin__", None)
        if origin is list:
            return {"type": "array"}
        elif origin is dict:
            return {"type": "object"}

        return {"type": "string"}

    def _resolve_schema_refs(self, schema: Any, defs: dict[str, Any]) -> Any:
        """Recursively resolve all $ref references inline within a JSON schema."""
        if not isinstance(schema, dict):
            return schema

        if "$ref" in schema:
            ref_path = schema["$ref"]
            if ref_path.startswith("#/$defs/"):
                def_name = ref_path.split("/")[-1]
                if def_name in defs:
                    resolved = defs[def_name].copy()
                    # Merge any extra keys (e.g. description) from the referencing schema
                    for key, value in schema.items():
                        if key != "$ref":
                            resolved[key] = value
                    return self._resolve_schema_refs(resolved, defs)
            return schema

        result: dict[str, Any] = {}
        for key, value in schema.items():
            if key == "$defs":
                continue
            elif key == "properties" and isinstance(value, dict):
                result[key] = {k: self._resolve_schema_refs(v, defs) for k, v in value.items()}
            elif key == "items" and isinstance(value, dict):
                result[key] = self._resolve_schema_refs(value, defs)
            elif key == "anyOf" and isinstance(value, list):
                result[key] = [self._resolve_schema_refs(v, defs) if isinstance(v, dict) else v for v in value]
            elif key == "allOf" and isinstance(value, list):
                result[key] = [self._resolve_schema_refs(v, defs) if isinstance(v, dict) else v for v in value]
            else:
                result[key] = value
        return result

    def get_mcp_tools(self) -> list[dict[str, Any]]:
        """
        Return MCP tools to be registered with the MCP server.

        Override this method to provide MCP tools, or use add_mcp_tool()
        to register tools dynamically.

        Returns:
            List of MCP tool definitions
        """
        return self._mcp_tools.copy()

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
