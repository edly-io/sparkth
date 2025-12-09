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

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

from fastapi import APIRouter
from starlette.middleware import Middleware
from sqlmodel import SQLModel


class SparkthPlugin:
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
        self._enabled = False
        
        # Internal storage for dynamically added components
        self._routes: List[APIRouter] = []
        self._models: List[Type[SQLModel]] = []
        self._mcp_tools: List[Dict[str, Any]] = []
        self._middleware: List[Middleware] = []
        self._dependencies: Dict[str, Callable] = {}
    
    # ==================== Lifecycle Methods ====================
    
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
        self._enabled = True
    
    def disable(self) -> None:
        """
        Disable the plugin.
        
        Called when the plugin is disabled. Use this to clean up resources,
        unregister hooks, or stop background tasks.
        
        Override this method to add custom disable logic.
        """
        self.enabled = False
        self._enabled = False
    
    # ==================== Route Registration ====================
    
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
        
        Returns:
            List of APIRouter instances
        """
        return self._routes.copy()
    
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
    
    # ==================== Database Models & Migrations ====================
    
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
    
    # ==================== MCP Tools ====================
    
    def add_mcp_tool(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        input_schema: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add an MCP tool to this plugin.
        
        Args:
            name: Tool name
            handler: Callable that handles the tool invocation
            description: Tool description
            input_schema: JSON Schema for tool input parameters
            
        Example:
            ```python
            def initialize(self):
                super().initialize()
                
                async def create_task_handler(title: str) -> str:
                    # Create task logic
                    return f"Created task: {title}"
                
                self.add_mcp_tool(
                    name="create_task",
                    handler=create_task_handler,
                    description="Create a new task",
                    input_schema={
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"}
                        }
                    }
                )
            ```
        """
        tool_def = {
            "name": name,
            "handler": handler,
            "description": description,
        }
        if input_schema:
            tool_def["inputSchema"] = input_schema
        self._mcp_tools.append(tool_def)
    
    def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """
        Return MCP tools to be registered with the MCP server.
        
        Override this method to provide MCP tools, or use add_mcp_tool()
        to register tools dynamically.
        
        Returns:
            List of MCP tool definitions
        """
        return self._mcp_tools.copy()
    
    # ==================== Middleware & Dependencies ====================
    
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
    
    def add_dependency(self, name: str, dependency: Callable) -> None:
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
    
    def get_dependencies(self) -> Dict[str, Callable]:
        """
        Return FastAPI dependencies to be registered globally.
        
        Override this method to provide dependencies, or use add_dependency()
        to register dependencies dynamically.
        
        Returns:
            Dictionary mapping dependency names to callables
        """
        return self._dependencies.copy()
    
    # ==================== Configuration ====================
    
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
    
    # ==================== Metadata & State ====================
    
    def is_initialized(self) -> bool:
        """Check if plugin has been initialized."""
        return self._initialized
    
    def is_enabled(self) -> bool:
        """Check if plugin is currently enabled."""
        return self._enabled
    
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
