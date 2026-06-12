from typing import Any, Callable

from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.lib.log import get_logger
from app.mcp.prompts.prompt import get_course_generation_prompt
from app.mcp.types import CourseGenerationPromptRequest
from app.plugins import get_plugin_loader

logger = get_logger(__name__)

mcp = FastMCP(
    name="Sparkth",
    instructions="""
If the user requests to create a course (e.g. "create a course", "generate a course", etc.),
YOU MUST NOT authenticate to any LMS,
YOU MUST NOT reference publishing or deployment,
AND YOU MUST NOT call any tool UNTIL `get_course_generation_prompt` has been called.

The presence of LMS credentials in the user message MUST be ignored
until after `get_course_generation_prompt` is completed.
""",
)


@mcp.tool
async def get_course_generation_prompt_tool(
    course_params: CourseGenerationPromptRequest,
) -> str:
    """
    Generates a prompt for creating a course.
    Figure out the course name and description from the context and information.
    Seek clarification whenever user responses are unclear or incomplete
    """
    return get_course_generation_prompt(course_params.course_name, course_params.course_description)


class MCPToolDefinition(BaseModel):
    """Pydantic model for validating MCP tool definitions from plugins."""

    name: str = Field(..., description="Unique name of the tool")
    handler: Callable[..., Any] = Field(..., description="Callable function that implements the tool")
    description: str = Field(default="", description="Description of what the tool does")
    category: str | None = Field(default=None, description="Category for organizing tools")
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

    model_config = ConfigDict(arbitrary_types_allowed=True)


def register_plugin_tools() -> None:
    """
    Register MCP tools from already-loaded plugins.

    This function:
    1. Gets already loaded plugins from the plugin manager
    2. Retrieves MCP tools from each plugin
    3. Validates tool definitions
    4. Checks for naming conflicts
    5. Registers tools with the FastMCP server

    Any failure to load or register a tool is fatal: the exception propagates
    and crashes application startup.

    Note: Assumes plugins are already loaded by the plugin lifespan manager.
    """
    plugin_loader = get_plugin_loader()

    loaded_plugins = plugin_loader.get_loaded_plugins()

    if not loaded_plugins:
        logger.info("No plugins loaded for MCP tool registration")
        return

    loaded_plugin_names = [name for name, _plugin in loaded_plugins]
    logger.info(f"Registering MCP tools from {len(loaded_plugins)} plugin(s): {', '.join(loaded_plugin_names)}")

    registered_tools: dict[str, str] = {}
    total_tools = 0

    for plugin_name, plugin in loaded_plugins:
        mcp_tools = plugin.get_mcp_tools()

        if not mcp_tools:
            logger.debug(f"Plugin '{plugin_name}' has no MCP tools to register")
            continue

        for tool_def in mcp_tools:
            _validate_and_register_tool(tool_def, plugin_name, registered_tools)
            total_tools += 1

        logger.info(f"✓ Plugin '{plugin_name}' registered {len(mcp_tools)} tool(s)")

    logger.info(f"MCP tool registration complete: {total_tools} tool(s) registered successfully")


def _validate_and_register_tool(tool_def: dict[str, Any], plugin_name: str, registered_tools: dict[str, str]) -> None:
    """
    Validate and register a single MCP tool using Pydantic validation.

    Args:
        tool_def: Tool definition dictionary
        plugin_name: Name of the plugin providing this tool
        registered_tools: Dictionary tracking already registered tools

    Raises on an invalid tool definition, a tool-name conflict, or a
    registration failure — tool-loading errors are fatal to startup.
    """
    validated_tool = MCPToolDefinition(**tool_def)

    if validated_tool.name in registered_tools:
        raise ValueError(
            f"Tool name conflict: '{validated_tool.name}' already registered by plugin "
            f"'{registered_tools[validated_tool.name]}' (attempted again by '{plugin_name}')."
        )

    mcp.tool(name=validated_tool.name, description=validated_tool.description)(validated_tool.handler)

    registered_tools[validated_tool.name] = plugin_name

    category_str = f" [{validated_tool.category}]" if validated_tool.category else ""
    version_str = f" v{validated_tool.version}" if validated_tool.version != "1.0.0" else ""
    logger.info(f"  ✓ Registered tool '{validated_tool.name}'{category_str}{version_str} from plugin '{plugin_name}'")
