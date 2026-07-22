from typing import Any, Callable

from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

from sparkth.lib.audit import audited_tool
from sparkth.lib.log import get_logger
from sparkth.lib.mcp.hooks import MCP_TOOLS, Tool
from sparkth.mcp.audit import ToolCallAuditMiddleware
from sparkth.mcp.prompts.prompt import get_course_generation_prompt
from sparkth.mcp.types import CourseGenerationPromptRequest

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
mcp.add_middleware(ToolCallAuditMiddleware())


# Tools registered directly on the server bypass the MCP_TOOLS hook (whose
# Tool dataclass audit-wraps handlers), so they must wrap explicitly.
@mcp.tool
@audited_tool
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
    Register MCP tools contributed by plugins with the FastMCP server.

    Reads the MCP_TOOLS hook and registers each tool, skipping name conflicts.
    Plugins must already be instantiated (which populates the hook); callers are
    responsible for that — the FastAPI lifespan and the standalone ``main`` below
    both load plugins before calling this.

    Any failure to load or register a tool is fatal: the exception propagates
    and crashes application startup.
    """
    registered_tools: dict[str, str] = {}
    total_tools = 0
    total_failed = 0

    for plugin, tool in MCP_TOOLS.iter_items():
        if _register_tool(tool, plugin.name, registered_tools):
            total_tools += 1
        else:
            total_failed += 1

        logger.info(
            f"MCP tool registration complete: {total_tools} tool(s) registered successfully"
            + (f", {total_failed} failed" if total_failed > 0 else "")
        )

    logger.info(f"MCP tool registration complete: {total_tools} tool(s) registered successfully")


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

    mcp.tool(name=tool.name, description=tool.description)(tool.handler)

    registered_tools[tool.name] = plugin_name

    category_str = f" [{tool.category}]" if tool.category else ""
    logger.info(f"  ✓ Registered tool '{tool.name}'{category_str} from plugin '{plugin_name}'")

    return True
