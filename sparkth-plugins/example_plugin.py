"""
Example Sparkth Plugin

This is a simple example plugin that demonstrates how to extend Sparkth
with custom functionality using the hooks system.

To use this plugin:
1. Copy this file to ~/.sparkth/sparkth-plugins/example_plugin.py
2. Enable it via the plugin manager
3. Restart the Sparkth application

Or install it as a package with an entrypoint in pyproject.toml:

[project.entry-points."sparkth.plugin.v1"]
example = "my_package.plugin"
"""

from fastapi import APIRouter

from app.hooks.catalog import Actions, Filters

# Plugin metadata
__version__ = "1.0.0"
__description__ = "Example plugin demonstrating the Sparkth plugin system"

# Create a custom API router
router = APIRouter(prefix="/example", tags=["example"])


@router.get("/hello")
async def hello():
    """A simple endpoint added by the plugin."""
    return {
        "message": "Hello from the example plugin!",
        "version": __version__,
    }


@router.get("/status")
async def status():
    """Return the plugin status."""
    return {
        "plugin": "example",
        "version": __version__,
        "status": "active",
        "description": __description__,
    }


# Register the router with Sparkth
Filters.API_ROUTERS.add_item(("example", router))


# Add a startup task
@Actions.APP_STARTUP.add()
def on_startup():
    """Called when the application starts."""
    print(f"Example plugin v{__version__} initialized!")


# Add a shutdown task
@Actions.APP_SHUTDOWN.add()
def on_shutdown():
    """Called when the application shuts down."""
    print("Example plugin shutting down...")


# Add configuration defaults
Filters.CONFIG_DEFAULTS.add_items([
    ("EXAMPLE_PLUGIN_ENABLED", True),
    ("EXAMPLE_PLUGIN_MESSAGE", "Hello from config!"),
])


# Listen to plugin lifecycle events
@Actions.PLUGIN_LOADED.add()
def on_plugin_loaded(plugin_name: str):
    """Called when any plugin is loaded."""
    if plugin_name == "example":
        print("Example plugin was loaded successfully!")


# Example of modifying data with filters
@Filters.PLUGINS_INFO.add()
def add_plugin_metadata(info_list):
    """Add custom metadata to the sparkth-plugins info list."""
    # This demonstrates how sparkth-plugins can modify data passing through filters
    return info_list


# Example MCP tool (if you want to add MCP functionality)
# Uncomment this if you have fastmcp available
"""
from fastmcp import FastMCP

mcp = FastMCP("example-plugin")

@mcp.tool
async def example_tool(text: str) -> str:
    '''
    An example MCP tool that echoes the input text.
    
    Args:
        text: The text to echo
    '''
    return f"Echo from example plugin: {text}"

# Register the MCP tool
Filters.MCP_TOOLS.add_item(mcp)
"""
