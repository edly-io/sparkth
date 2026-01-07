from fastmcp import FastMCP

from app.core.config import get_settings
from app.mcp.oauth_provider import SparkthOAuthProvider
from app.mcp.prompts.prompt import get_course_generation_prompt
from app.mcp.types import CourseGenerationPromptRequest

settings = get_settings()

# Create OAuth provider instance
oauth_provider = SparkthOAuthProvider()

# Configure MCP server with OAuth support
mcp = FastMCP(
    "Sparkth",
    instructions="AI-powered course generation with OAuth authentication",
    auth=oauth_provider,  # Use our custom OAuth provider
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
