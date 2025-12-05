from fastmcp import FastMCP

from sparkth_mcp.types import CourseGenerationPromptRequest
from sparkth_mcp.prompts.prompt import get_course_generation_prompt

mcp = FastMCP("Sparkth")


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
