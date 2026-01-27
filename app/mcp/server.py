from fastmcp import FastMCP

from app.mcp.prompts.prompt import get_course_generation_prompt
from app.mcp.types import CourseGenerationPromptRequest

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
