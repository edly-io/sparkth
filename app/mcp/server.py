from fastmcp import FastMCP

from app.lib.log import get_logger
from app.lib.mcp.hooks import MCP_TOOLS, Tool
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
