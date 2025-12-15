import argparse
import logging
import sys
from pathlib import Path

from app.mcp.canvas.tools import *  # noqa
from app.mcp.mode import TransportMode
from app.mcp.openedx.tools import *  # noqa
from app.mcp.server import mcp
from app.plugins import PluginManager


# Add app directory to path for plugin imports
app_path = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(app_path.parent))

logger = logging.getLogger(__name__)


def register_plugin_tools():
    """
    Discover and register MCP tools from enabled plugins.

    This function:
    1. Loads all enabled plugins
    2. Retrieves MCP tools from each plugin
    3. Validates tool definitions
    4. Checks for naming conflicts
    5. Registers tools with the FastMCP server
    """
    try:
        # Initialize plugin manager
        plugin_manager = PluginManager()

        # Load all enabled plugins
        loaded_plugins = plugin_manager.load_all_enabled()

        if not loaded_plugins:
            logger.info("No plugins loaded for MCP tool registration")
            return

        logger.info(f"Loaded {len(loaded_plugins)} plugin(s) for MCP: {', '.join(loaded_plugins.keys())}")

        # Enable plugins
        plugin_manager.enable_all_loaded()

        # Track registered tools to detect conflicts
        registered_tools = {}
        total_tools = 0
        total_failed = 0

        # Register MCP tools from each plugin
        for plugin_name, plugin in loaded_plugins.items():
            plugin_tool_count = 0
            plugin_failed_count = 0

            try:
                mcp_tools = plugin.get_mcp_tools()

                if not mcp_tools:
                    logger.debug(f"Plugin '{plugin_name}' has no MCP tools to register")
                    continue

                for tool_def in mcp_tools:
                    try:
                        # Validate and register tool
                        success = _validate_and_register_tool(tool_def, plugin_name, registered_tools)

                        if success:
                            plugin_tool_count += 1
                            total_tools += 1
                        else:
                            plugin_failed_count += 1
                            total_failed += 1

                    except Exception as e:
                        logger.error(f"Failed to register tool from plugin '{plugin_name}': {e}")
                        plugin_failed_count += 1
                        total_failed += 1

                # Log summary for this plugin
                if plugin_tool_count > 0:
                    logger.info(
                        f"✓ Plugin '{plugin_name}' registered {plugin_tool_count} tool(s)"
                        + (f" ({plugin_failed_count} failed)" if plugin_failed_count > 0 else "")
                    )
                elif plugin_failed_count > 0:
                    logger.warning(f"Plugin '{plugin_name}' failed to register {plugin_failed_count} tool(s)")

            except Exception as e:
                logger.error(f"Failed to process MCP tools from plugin '{plugin_name}': {e}")

        # Log overall summary
        logger.info(
            f"MCP tool registration complete: {total_tools} tool(s) registered successfully"
            + (f", {total_failed} failed" if total_failed > 0 else "")
        )

    except Exception as e:
        logger.error(f"Failed to initialize plugin system for MCP: {e}")


def _validate_and_register_tool(tool_def: dict, plugin_name: str, registered_tools: dict) -> bool:
    """
    Validate and register a single MCP tool.

    Args:
        tool_def: Tool definition dictionary
        plugin_name: Name of the plugin providing this tool
        registered_tools: Dictionary tracking already registered tools

    Returns:
        True if tool was successfully registered, False otherwise
    """
    # Extract tool details
    tool_name = tool_def.get("name")
    tool_handler = tool_def.get("handler")
    tool_description = tool_def.get("description", "")
    tool_category = tool_def.get("category")
    tool_version = tool_def.get("version", "1.0.0")

    # Validate tool name
    if not tool_name:
        logger.warning(f"Tool from plugin '{plugin_name}' is missing a name. Skipping.")
        return False

    # Validate tool handler
    if not tool_handler:
        logger.warning(f"Tool '{tool_name}' from plugin '{plugin_name}' is missing a handler. Skipping.")
        return False

    # Check if handler is callable
    if not callable(tool_handler):
        logger.warning(f"Tool '{tool_name}' from plugin '{plugin_name}' has a non-callable handler. Skipping.")
        return False

    # Check for duplicate tool names
    if tool_name in registered_tools:
        logger.warning(
            f"Tool name conflict: '{tool_name}' already registered by plugin "
            f"'{registered_tools[tool_name]}'. Skipping registration from '{plugin_name}'."
        )
        return False

    # Register tool with FastMCP
    try:
        mcp.tool(name=tool_name, description=tool_description)(tool_handler)

        # Track the registered tool
        registered_tools[tool_name] = plugin_name

        # Log success with details
        category_str = f" [{tool_category}]" if tool_category else ""
        version_str = f" v{tool_version}" if tool_version != "1.0.0" else ""
        logger.info(f"  ✓ Registered tool '{tool_name}'{category_str}{version_str} from plugin '{plugin_name}'")

        return True

    except Exception as e:
        logger.error(f"Failed to register tool '{tool_name}' from plugin '{plugin_name}': {e}")
        return False


def run_stdio():
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
