"""
SparkthPlugin Base Class

Provides the foundation for all Sparkth plugins with support for:
- Route registration
- Database models and migrations
- MCP tools
- Middleware and dependencies
- Configuration management
- Lifecycle hooks
"""

import inspect
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, get_type_hints

from fastapi import APIRouter
from sqlmodel import SQLModel
from starlette.middleware import Middleware

from app.core.logger import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def tool(
    name: Optional[str] = None,
    description: str = "",
    category: Optional[str] = None,
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

    _tool_registry: Dict[str, Dict[str, Any]]

    def __new__(
        mcs: Type["PluginMeta"], name: str, bases: tuple[Type[Any], ...], namespace: Dict[str, Any]
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

        Example:
    ```python
            class MyPlugin(SparkthPlugin):
                def __init__(self):
                    super().__init__(
                        name="my-plugin",
                        version="1.0.0",
                        description="My awesome plugin",
                        author="Your Name"
                    )

                def get_routes(self) -> List[APIRouter]:
                    router = APIRouter()

                    @router.get("/my-endpoint")
                    def my_endpoint():
                        return {"message": "Hello from plugin!"}

                    return [router]
    ```
    """

    _tool_registry: Dict[str, Dict[str, Any]]

    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        description: str = "",
        author: str = "",
        dependencies: Optional[List[str]] = None,
        enabled: bool = True,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the plugin with metadata.
        
        Args:
            name: Unique identifier for the plugin (e.g., "tasks-plugin")
            version: Semantic version string (e.g., "1.0.0")
            description: Brief description of plugin functionality
            author: Plugin author name or organization
            dependencies: List of other plugin names this plugin depends on
            enabled: Whether the plugin is enabled by default
            config: Plugin-specific configuration dictionary
        """
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.dependencies = dependencies or []
        self.enabled = enabled
        self.config = config or {}
        self._initialized = False
        self._routes: List[APIRouter] = []
        self._models: List[Type[SQLModel]] = []
        self._mcp_tools: List[Dict[str, Any]] = []
        self._middleware: List[Middleware] = []
        self._dependencies: Dict[str, Callable[..., Any]] = {}

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

            except Exception as e:
                logger.error(f"Failed to auto-register tool from method '{method_name}' in plugin '{self.name}': {e}")

    def initialize(self) -> None:
        """
        Initialize the plugin.

        Called once when the plugin is first loaded. Use this to set up
        any resources, validate configuration, or prepare the plugin for use.
        This is called before enable().

        Override this method to add custom initialization logic.
        """
        self._initialized = True

    def enable(self) -> None:
        """
        Enable the plugin.

        Called when the plugin is enabled. Use this to register hooks,
        start background tasks, or perform any enable-specific logic.

        Override this method to add custom enable logic.
        """
        self.enabled = True

    def disable(self) -> None:
        """
        Disable the plugin.

        Called when the plugin is disabled. Use this to clean up resources,
        unregister hooks, or stop background tasks.

        Override this method to add custom disable logic.
        """
        self.enabled = False

    def add_route(self, router: APIRouter) -> None:
        """
                Add a FastAPI router to this plugin.

                Args:
                    router: APIRouter instance to add

                Example:
        ```python
                    def initialize(self):
                        super().initialize()
                        router = APIRouter(prefix="/tasks", tags=["Tasks"])

                        @router.get("/")
                        def list_tasks():
                            return {"tasks": []}

                        self.add_route(router)
        ```
        """
        self._routes.append(router)

    def get_routes(self) -> List[APIRouter]:
        """
        Return FastAPI routers to be registered with the application.

        Override this method to provide custom API endpoints, or use add_route()
        to register routes dynamically.

        All routes are automatically tagged with plugin metadata for access control.

        Returns:
            List of APIRouter instances
        """
        routes = self._routes.copy()
        for router in routes:
            self._tag_router_with_plugin(router)
        return routes

    def _tag_router_with_plugin(self, router: APIRouter) -> None:
        """
        Tag all routes in a router with plugin metadata.

        This adds the plugin name to each route's tags for identification
        by the PluginAccessMiddleware.

        Args:
            router: APIRouter to tag
        """
        plugin_tag = f"plugin:{self.name}"
        if router.tags:
            if plugin_tag not in router.tags:
                router.tags.append(plugin_tag)
        else:
            router.tags = [plugin_tag]

        for route in router.routes:
            if hasattr(route, "endpoint"):
                setattr(route.endpoint, "__plugin_name__", self.name)

    def get_route_prefix(self) -> Optional[str]:
        """
        Return a prefix to be applied to all routes from this plugin.

        If None, routes will be registered at the root level.
        If provided, all plugin routes will be prefixed with this path.

        Returns:
            Optional path prefix (e.g., "/plugins/my-plugin")
        """
        return None

    def get_route_tags(self) -> List[str]:
        """
        Return OpenAPI tags to be applied to all routes from this plugin.

        Returns:
            List of tag strings for route categorization
        """
        return [self.name]

    def add_model(self, model: Type[SQLModel]) -> None:
        """
                Add a SQLModel class to this plugin.

                Args:
                    model: SQLModel class to add

                Example:
        ```python
                    def initialize(self):
                        super().initialize()

                        class Task(SQLModel, table=True):
                            id: Optional[int] = Field(primary_key=True)
                            title: str
                            completed: bool = False

                        self.add_model(Task)
        ```
        """
        self._models.append(model)

    def get_models(self) -> List[Type[SQLModel]]:
        """
        Return SQLModel classes to be registered with the application.

        Override this method to provide database models, or use add_model()
        to register models dynamically.

        Returns:
            List of SQLModel class types
        """
        return self._models.copy()

    def get_migrations_path(self) -> Optional[Path]:
        """
        Return the path to Alembic migration files for this plugin.

        If your plugin includes database schema changes, provide the
        directory containing migration version files.

        Returns:
            Path to migrations directory, or None if no migrations
        """
        return None

    def get_migration_dependencies(self) -> List[str]:
        """
        Return list of migration revision IDs this plugin's migrations depend on.

        Use this to ensure migrations are run in the correct order.

        Returns:
            List of Alembic revision IDs
        """
        return []

    def add_mcp_tool(
        self,
        name: str,
        handler: Callable[..., Any],
        description: str = "",
        input_schema: Optional[Dict[str, Any]] = None,
        category: Optional[str] = None,
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

                Example:
        ```python
                    def initialize(self):
                        super().initialize()

                        async def create_task_handler(title: str) -> str:
                            return f"Created task: {title}"

                        self.add_mcp_tool(
                            name="create_task",
                            handler=create_task_handler,
                            description="Create a new task",
                            category="tasks",
                            version="1.0.0"
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

    def _generate_input_schema(self, func: Callable[..., Any]) -> Dict[str, Any]:
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

            properties: Dict[str, Any] = {}
            required: List[str] = []

            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue

                param_type = type_hints.get(param_name, str)
                properties[param_name] = self._type_to_json_schema(param_type)

                if param.default == inspect.Parameter.empty:
                    required.append(param_name)

            schema: Dict[str, Any] = {
                "type": "object",
                "properties": properties,
            }

            if required:
                schema["required"] = required

            return schema

        except Exception as e:
            logger.warning(f"Failed to generate input schema for {func.__name__}: {e}. Using empty schema.")
            return {"type": "object", "properties": {}}

    def _type_to_json_schema(self, py_type: Type[Any]) -> Dict[str, Any]:
        """
        Convert Python type to JSON Schema type definition.

        Args:
            py_type: Python type to convert

        Returns:
            JSON Schema type definition
        """
        type_map: Dict[Type[Any], Dict[str, str]] = {
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

    def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """
        Return MCP tools to be registered with the MCP server.

        Override this method to provide MCP tools, or use add_mcp_tool()
        to register tools dynamically.

        Returns:
            List of MCP tool definitions
        """
        return self._mcp_tools.copy()

    def add_middleware(self, middleware: Middleware) -> None:
        """
                Add FastAPI middleware to this plugin.

                Args:
                    middleware: Middleware instance to add

                Example:
        ```python
                    def initialize(self):
                        super().initialize()
                        from starlette.middleware.cors import CORSMiddleware

                        self.add_middleware(
                            Middleware(
                                CORSMiddleware,
                                allow_origins=["*"],
                                allow_methods=["*"]
                            )
                        )
        ```
        """
        self._middleware.append(middleware)

    def add_dependency(self, name: str, dependency: Callable[..., Any]) -> None:
        """
        Add a FastAPI dependency to this plugin.

        Args:
            name: Dependency name
            dependency: Callable dependency function
        """
        self._dependencies[name] = dependency

    def get_middleware(self) -> List[Middleware]:
        """
        Return FastAPI middleware to be added to the application.

        Override this method to provide middleware, or use add_middleware()
        to register middleware dynamically.

        Returns:
            List of Middleware instances
        """
        return self._middleware.copy()

    def get_dependencies(self) -> Dict[str, Callable[..., Any]]:
        """
        Return FastAPI dependencies to be registered globally.

        Override this method to provide dependencies, or use add_dependency()
        to register dependencies dynamically.

        Returns:
            Dictionary mapping dependency names to callables
        """
        return self._dependencies.copy()
    
    def get_config_schema(self) -> Optional[Dict[str, Any]]:
        """
        Return JSON Schema for plugin configuration validation.

        Override this method to define expected configuration structure.

        Returns:
            JSON Schema dictionary, or None for no validation
        """
        return None

    def get_default_config(self) -> Dict[str, Any]:
        """
        Return default configuration values for the plugin.

        Override this method to provide sensible defaults.

        Returns:
            Dictionary of default configuration values
        """
        return {}

    def update_config(self, config: Dict[str, Any]) -> None:
        """
        Update plugin configuration.

        Args:
            config: New configuration dictionary
        """
        self.config.update(config)

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by key.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)

    def is_initialized(self) -> bool:
        """Check if plugin has been initialized."""
        return self._initialized

    def is_enabled(self) -> bool:
        """Check if plugin is currently enabled."""
        return self.enabled

    def get_info(self) -> Dict[str, Any]:
        """
        Return plugin metadata and state information.

        Returns:
            Dictionary containing plugin information
        """
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "dependencies": self.dependencies,
            "enabled": self.enabled,
            "initialized": self._initialized,
            "config": self.config,
        }
    
    def __repr__(self) -> str:
        """Return string representation of the plugin."""
        return f"<SparkthPlugin: {self.name} v{self.version}>"
