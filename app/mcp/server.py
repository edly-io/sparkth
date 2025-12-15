from fastmcp import FastMCP

from app.mcp.prompts.prompt import get_course_generation_prompt
from app.mcp.types import CourseGenerationPromptRequest

mcp = FastMCP("Sparkth")

# Import tools to register them with the mcp instance
from app.mcp.canvas.tools import *  # noqa: F401, F403, E402
from app.mcp.openedx.tools import *  # noqa: F401, F403, E402


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
