import argparse
import asyncio

from app.lib.log import configure_logging, get_logger
from app.lib.mcp.hooks import MCP_TOOLS, Tool
from app.mcp.mode import TransportMode
from app.mcp.server import mcp
from app.plugins import get_plugin_loader

logger = get_logger(__name__)


def register_plugin_tools() -> None:
    """
    Register MCP tools contributed by plugins with the FastMCP server.

    Instantiates plugins (so they populate the MCP_TOOLS hook), then registers each
    tool, skipping name conflicts.
    """
    try:
        # Instantiate plugins so their tools are contributed to the MCP_TOOLS hook.
        get_plugin_loader()

        registered_tools: dict[str, str] = {}
        total_tools = 0
        total_failed = 0

        for plugin, tool in MCP_TOOLS.iter_items():
            try:
                if _register_tool(tool, plugin.name, registered_tools):
                    total_tools += 1
                else:
                    total_failed += 1
            except (ValueError, TypeError) as e:
                logger.error(f"Failed to register tool from plugin '{plugin.name}': {e}")
                total_failed += 1

        logger.info(
            f"MCP tool registration complete: {total_tools} tool(s) registered successfully"
            + (f", {total_failed} failed" if total_failed > 0 else "")
        )

    except RuntimeError as e:
        logger.error(f"Failed to initialize plugin system for MCP: {e}")


def _register_tool(tool: Tool, plugin_name: str, registered_tools: dict[str, str]) -> bool:
    """
    Register a single MCP tool with the FastMCP server.

    Args:
        tool: The tool contributed by the plugin
        plugin_name: Name of the plugin providing this tool
        registered_tools: Dictionary tracking already registered tools

    Returns:
        True if tool was successfully registered, False otherwise
    """
    if tool.name in registered_tools:
        logger.warning(
            f"Tool name conflict: '{tool.name}' already registered by plugin "
            f"'{registered_tools[tool.name]}'. Skipping registration from '{plugin_name}'."
        )
        return False
    try:
        mcp.tool(name=tool.name, description=tool.description)(tool.handler)

        registered_tools[tool.name] = plugin_name

        category_str = f" [{tool.category}]" if tool.category else ""
        logger.info(f"  ✓ Registered tool '{tool.name}'{category_str} from plugin '{plugin_name}'")

        return True

    except (ValueError, TypeError, RuntimeError) as e:
        logger.error(f"Failed to register tool '{tool.name}' from plugin '{plugin_name}': {e}")
        return False


def run_stdio() -> None:
    mcp.run()


def run_http(host: str, port: int) -> None:
    mcp.run(transport="http", host=host, port=port)


def main() -> None:
    configure_logging()

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

    register_plugin_tools()
    all_tools = asyncio.run(mcp.get_tools())
    print(f"MCP server starting with {len(all_tools)} total tool(s) registered")

    if transport_mode == TransportMode.STDIO:
        run_stdio()
    else:
        run_http(args.host, args.port)


if __name__ == "__main__":
    main()
