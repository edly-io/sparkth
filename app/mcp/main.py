import argparse
import asyncio
import logging
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field, field_validator

from app.mcp.mode import TransportMode
from app.mcp.server import mcp
from app.plugins import get_plugin_manager

logger = logging.getLogger(__name__)


class MCPToolDefinition(BaseModel):
    """Pydantic model for validating MCP tool definitions from plugins."""

    name: str = Field(..., description="Unique name of the tool")
    handler: Callable[..., Any] = Field(..., description="Callable function that implements the tool")
    description: str = Field(default="", description="Description of what the tool does")
    category: Optional[str] = Field(default=None, description="Category for organizing tools")
    version: str = Field(default="1.0.0", description="Version of the tool")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that the tool name is not empty."""
        if not v or not v.strip():
            raise ValueError("Tool name cannot be empty")
        return v.strip()

    @field_validator("handler")
    @classmethod
    def validate_handler(cls, v: Any) -> Callable[..., Any]:
        """Validate that the handler is callable."""
        if not callable(v):
            raise ValueError("Tool handler must be callable")
        handler: Callable[..., Any] = v
        return handler

    class Config:
        arbitrary_types_allowed = True


def register_plugin_tools() -> None:
    """
    Register MCP tools from already-loaded plugins.

    This function:
    1. Gets already loaded plugins from the plugin manager
    2. Retrieves MCP tools from each plugin
    3. Validates tool definitions
    4. Checks for naming conflicts
    5. Registers tools with the FastMCP server

    Note: Assumes plugins are already loaded by the plugin lifespan manager.
    """
    try:
        plugin_manager = get_plugin_manager()

        loaded_plugins = plugin_manager.get_loaded_plugins()

        if not loaded_plugins:
            logger.info("No plugins loaded for MCP tool registration")
            return

        logger.info(f"Registering MCP tools from {len(loaded_plugins)} plugin(s): {', '.join(loaded_plugins.keys())}")

        registered_tools: dict[str, str] = {}
        total_tools = 0
        total_failed = 0

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

                if plugin_tool_count > 0:
                    logger.info(
                        f"✓ Plugin '{plugin_name}' registered {plugin_tool_count} tool(s)"
                        + (f" ({plugin_failed_count} failed)" if plugin_failed_count > 0 else "")
                    )
                elif plugin_failed_count > 0:
                    logger.warning(f"Plugin '{plugin_name}' failed to register {plugin_failed_count} tool(s)")

            except Exception as e:
                logger.error(f"Failed to process MCP tools from plugin '{plugin_name}': {e}")

        logger.info(
            f"MCP tool registration complete: {total_tools} tool(s) registered successfully"
            + (f", {total_failed} failed" if total_failed > 0 else "")
        )

    except Exception as e:
        logger.error(f"Failed to initialize plugin system for MCP: {e}")


def _validate_and_register_tool(tool_def: dict[str, Any], plugin_name: str, registered_tools: dict[str, str]) -> bool:
    """
    Validate and register a single MCP tool using Pydantic validation.

    Args:
        tool_def: Tool definition dictionary
        plugin_name: Name of the plugin providing this tool
        registered_tools: Dictionary tracking already registered tools

    Returns:
        True if tool was successfully registered, False otherwise
    """
    try:
        validated_tool = MCPToolDefinition(**tool_def)
    except Exception as e:
        logger.warning(f"Invalid tool definition from plugin '{plugin_name}': {e}")
        return False

    if validated_tool.name in registered_tools:
        logger.warning(
            f"Tool name conflict: '{validated_tool.name}' already registered by plugin "
            f"'{registered_tools[validated_tool.name]}'. Skipping registration from '{plugin_name}'."
        )
        return False
    try:
        mcp.tool(name=validated_tool.name, description=validated_tool.description)(validated_tool.handler)

        registered_tools[validated_tool.name] = plugin_name

        category_str = f" [{validated_tool.category}]" if validated_tool.category else ""
        version_str = f" v{validated_tool.version}" if validated_tool.version != "1.0.0" else ""
        logger.info(
            f"  ✓ Registered tool '{validated_tool.name}'{category_str}{version_str} from plugin '{plugin_name}'"
        )

        return True

    except Exception as e:
        logger.error(f"Failed to register tool '{validated_tool.name}' from plugin '{plugin_name}': {e}")
        return False


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

    register_plugin_tools()
    all_tools = asyncio.run(mcp.get_tools())
    print(f"MCP server starting with {len(all_tools)} total tool(s) registered")

    if transport_mode == TransportMode.STDIO:
        run_stdio()
    else:
        run_http(args.host, args.port)


if __name__ == "__main__":
    main()
