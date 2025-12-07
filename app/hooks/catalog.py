"""
List of all the action and filter names used across Sparkth.

This module is the central catalog of all available Actions and Filters
that sparkth-plugins can use to extend and modify the Sparkth application.
"""

from __future__ import annotations

from typing import Any, Callable, Tuple

from fastapi import APIRouter

from .actions import Action
from .filters import Filter

__all__ = ["Actions", "Filters"]


class Actions:
    """
    Container for all actions used across Sparkth.

    Actions are used to trigger callback functions at specific moments in the
    Sparkth lifecycle. To create a new callback for an existing action, start by
    importing the hooks module::

        from app import hooks

    Then create your callback function and decorate it with the :py:meth:`add` method::

        @hooks.Actions.PLUGIN_LOADED.add()
        def on_plugin_loaded(plugin_name: str):
            print(f"Plugin {plugin_name} was loaded!")

    Your callback function will be called whenever the action is triggered.
    Note that action callbacks do not return anything.
    """

    #: Triggered when the core application is ready to run.
    #:
    #: This is the right time to discover sparkth-plugins. This action is called as soon
    #: as possible during application initialization.
    #:
    #: Plugins are auto-discovered from:
    #: - Python packages that declare a "sparkth.plugin.v1" entrypoint
    #: - Python files in the sparkth-plugins directory
    #:
    #: This action does not have any parameters.
    CORE_READY: Action[[]] = Action()

    #: Triggered when a single plugin needs to be loaded.
    #:
    #: Only sparkth-plugins that have previously been discovered can be loaded.
    #: Plugins are typically loaded because they were enabled by the user.
    #:
    #: Most plugin developers will not have to implement this action themselves,
    #: unless they want to perform a specific action at the moment the plugin is enabled.
    #:
    #: :parameter str plugin: plugin name
    PLUGIN_LOADED: Action[[str]] = Action()

    #: Triggered after all sparkth-plugins have been loaded.
    #:
    #: At this point the list of loaded sparkth-plugins may be obtained from the
    #: :py:data:`Filters.PLUGINS_LOADED` filter.
    #:
    #: This action does not have any parameters.
    PLUGINS_LOADED: Action[[]] = Action()

    #: Triggered when a single plugin is unloaded.
    #:
    #: Only sparkth-plugins that have previously been loaded can be unloaded.
    #: Plugins are typically unloaded because they were disabled by the user.
    #:
    #: Most plugin developers will not have to implement this action themselves,
    #: unless they want to perform a specific action at the moment the plugin is disabled.
    #:
    #: :parameter str plugin: plugin name
    PLUGIN_UNLOADED: Action[[str]] = Action()

    #: Triggered when the FastAPI application starts up.
    #:
    #: This is called during the FastAPI startup event, after all sparkth-plugins have been loaded.
    #: Use this to initialize resources, start background tasks, etc.
    #:
    #: This action does not have any parameters.
    APP_STARTUP: Action[[]] = Action()

    #: Triggered when the FastAPI application shuts down.
    #:
    #: This is called during the FastAPI shutdown event.
    #: Use this to clean up resources, close connections, etc.
    #:
    #: This action does not have any parameters.
    APP_SHUTDOWN: Action[[]] = Action()


class Filters:
    """
    Container for all filters used across Sparkth.

    Filters are used to modify data at specific points during the Sparkth lifecycle.
    To add a callback to an existing filter, start by importing the hooks module::

        from app import hooks

    Then create your callback function and decorate it with the :py:meth:`add` method::

        @hooks.Filters.API_ROUTERS.add()
        def add_my_router(routers: list[Tuple[str, APIRouter]]) -> list[Tuple[str, APIRouter]]:
            from my_plugin import router
            routers.append(("my-plugin", router))
            return routers

    Note that your filter callback should have the same signature as the original
    filter. The return value should also have the same type as the first argument.

    Many filters have a list of items as the first argument. In such cases, you can
    use the ``add_item`` or ``add_items`` methods instead::

        from my_plugin import router
        hooks.Filters.API_ROUTERS.add_item(("my-plugin", router))
    """

    #: List of installed sparkth-plugins.
    #:
    #: This filter contains all sparkth-plugins that have been discovered, regardless of
    #: whether they are enabled or not.
    #:
    #: :parameter list[str] sparkth-plugins: list of plugin names
    PLUGINS_INSTALLED: Filter[list[str], []] = Filter()

    #: List of loaded (enabled) sparkth-plugins.
    #:
    #: This filter contains only the sparkth-plugins that are currently enabled and loaded.
    #:
    #: :parameter list[str] sparkth-plugins: list of plugin names
    PLUGINS_LOADED: Filter[list[str], []] = Filter()

    #: Information about each installed plugin, including its version.
    #:
    #: Keep this information to a single line for easier parsing.
    #:
    #: :parameter list[tuple[str, str]] versions: each pair is a (plugin, info) tuple
    PLUGINS_INFO: Filter[list[tuple[str, str]], []] = Filter()

    #: List of FastAPI routers to be included in the application.
    #:
    #: Each item is a tuple of (prefix, router) where:
    #: - prefix: URL prefix for the router (e.g., "/my-plugin")
    #: - router: FastAPI APIRouter instance
    #:
    #: These routers will be automatically included in the main FastAPI application.
    #:
    #: :parameter list[tuple[str, APIRouter]] routers: list of (prefix, router) tuples
    API_ROUTERS: Filter[list[tuple[str, APIRouter]], []] = Filter()

    #: List of MCP (Model Context Protocol) server instances to register.
    #:
    #: Plugins can add their MCP servers here, and they will be integrated
    #: with the main Sparkth MCP server.
    #:
    #: :parameter list[Any] servers: list of MCP server instances
    MCP_SERVERS: Filter[list[Any], []] = Filter()

    #: List of MCP tools to be registered.
    #:
    #: Plugins can add their MCP tool functions here. Each tool should be
    #: decorated with the @mcp.tool decorator from the FastMCP library.
    #:
    #: :parameter list[Callable] tools: list of MCP tool functions
    MCP_TOOLS: Filter[list[Callable[..., Any]], []] = Filter()

    #: Declare new default configuration settings.
    #:
    #: Default settings may be overridden by user configuration.
    #: All new entries must be prefixed with the plugin name in all-caps.
    #:
    #: :parameter list[tuple[str, Any]] items: list of (name, value) settings
    CONFIG_DEFAULTS: Filter[list[tuple[str, Any]], []] = Filter()

    #: Modify existing configuration settings.
    #:
    #: Beware not to override important settings like passwords!
    #: Overridden setting values should be backed up by users.
    #:
    #: :parameter list[tuple[str, Any]] items: list of (name, value) settings
    CONFIG_OVERRIDES: Filter[list[tuple[str, Any]], []] = Filter()

    #: Declare unique configuration settings that must be saved.
    #:
    #: This is where you should declare passwords and randomly-generated values
    #: that are different from one environment to the next.
    #:
    #: All names must be prefixed with the plugin name in all-caps.
    #:
    #: :parameter list[tuple[str, Any]] items: list of (name, value) settings
    CONFIG_UNIQUE: Filter[list[tuple[str, Any]], []] = Filter()

    #: List of middleware to be added to the FastAPI application.
    #:
    #: Each middleware should be a callable that takes the app and returns None.
    #:
    #: :parameter list[Callable] middleware: list of middleware callables
    API_MIDDLEWARE: Filter[list[Callable[[Any], None]], []] = Filter()

    #: List of startup tasks to run when the application starts.
    #:
    #: Each task is a tuple of (name, callable) where the callable is an async function.
    #:
    #: :parameter list[tuple[str, Callable]] tasks: list of (name, task) tuples
    STARTUP_TASKS: Filter[list[tuple[str, Callable[[], Any]]], []] = Filter()

    #: List of shutdown tasks to run when the application stops.
    #:
    #: Each task is a tuple of (name, callable) where the callable is an async function.
    #:
    #: :parameter list[tuple[str, Callable]] tasks: list of (name, task) tuples
    SHUTDOWN_TASKS: Filter[list[tuple[str, Callable[[], Any]]], []] = Filter()

    #: List of SQLModel model classes from plugins.
    #:
    #: Plugins register their database models here so they can be included
    #: in Alembic migrations. Each model should be a SQLModel class with table=True.
    #:
    #: :parameter list[type] models: list of SQLModel classes
    SQLMODEL_MODELS: Filter[list[type], []] = Filter()
