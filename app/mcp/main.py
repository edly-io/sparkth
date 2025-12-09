import argparse
import logging
import sys
from pathlib import Path

from app.mcp.canvas.tools import *  # noqa
from app.mcp.mode import TransportMode
from app.mcp.openedx.tools import *  # noqa
from app.mcp.server import mcp


# Add app directory to path for plugin imports
app_path = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(app_path.parent))

from app.plugins import PluginManager

logger = logging.getLogger(__name__)


def register_plugin_tools():
    """
    Discover and register MCP tools from enabled plugins.
    """
    try:
        # Initialize plugin manager
        plugin_manager = PluginManager()
        
        # Load all enabled plugins
        loaded_plugins = plugin_manager.load_all_enabled()
        
        if loaded_plugins:
            logger.info(f"Loaded {len(loaded_plugins)} plugin(s) for MCP: {', '.join(loaded_plugins.keys())}")
        
        # Enable plugins
        plugin_manager.enable_all_loaded()
        
        # Register MCP tools from each plugin
        for plugin_name, plugin in loaded_plugins.items():
            try:
                mcp_tools = plugin.get_mcp_tools()
                if mcp_tools:
                    for tool_def in mcp_tools:
                        # Get tool details
                        tool_name = tool_def.get("name")
                        tool_handler = tool_def.get("handler")
                        tool_description = tool_def.get("description", "")
                        
                        if tool_name and tool_handler:
                            # Register tool with FastMCP using decorator
                            mcp.tool(name=tool_name, description=tool_description)(tool_handler)
                            logger.info(f"Registered MCP tool '{tool_name}' from plugin '{plugin_name}'")
                        
            except Exception as e:
                logger.error(f"Failed to register MCP tools from plugin '{plugin_name}': {e}")
        
    except Exception as e:
        logger.error(f"Failed to initialize plugin system for MCP: {e}")


def run_stdio() -> None:
    mcp.run()


def run_http(host: str, port: int) -> None:
    mcp.run(transport="http", host=host, port=port)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--transport",
        default="http",
        choices=[mode.value for mode in TransportMode],
        help="MCP server transport mode",
    )
    parser.add_argument("--host", default="0.0.0.0", help="MCP server host")
    parser.add_argument("--port", type=int, default=7727, help="MCP server port")

    args = parser.parse_args()
    transport_mode = TransportMode(args.transport)

    # Register plugin tools before starting server
    register_plugin_tools()
    
    # Log total number of registered MCP tools (core + plugin tools)
    import asyncio
    all_tools = asyncio.run(mcp.get_tools())
    print(f"MCP server starting with {len(all_tools)} total tool(s) registered")

    if transport_mode == TransportMode.STDIO:
        run_stdio()
    else:
        run_http(args.host, args.port)


if __name__ == "__main__":
    main()
