"""The language handling of the MCP course-generation prompt and its tool.

The MCP server has no identity layer, so the language cannot be resolved from a user —
the calling agent supplies it, and anything unusable falls back to the platform default.
"""

import pytest
from fastmcp import Client

from sparkth.lib.language import SUPPORTED_LANGUAGES
from sparkth.lib.settings import get_settings
from sparkth.mcp.prompts.prompt import get_course_generation_prompt
from sparkth.mcp.server import mcp
from sparkth.mcp.types import CourseGenerationPromptRequest


class TestCourseGenerationPromptLanguage:
    @pytest.mark.parametrize("tag", sorted(SUPPORTED_LANGUAGES))
    def test_names_the_language_for_every_supported_tag(self, tag: str) -> None:
        prompt = get_course_generation_prompt("Data Privacy", "An intro course", tag)
        assert SUPPORTED_LANGUAGES[tag].name in prompt

    @pytest.mark.parametrize("tag", sorted(SUPPORTED_LANGUAGES))
    def test_no_unrendered_placeholder_remains(self, tag: str) -> None:
        prompt = get_course_generation_prompt("Data Privacy", "An intro course", tag)
        assert "{language_name}" not in prompt

    def test_ambiguous_language_instruction_is_gone(self) -> None:
        """ "in the user's language" is undefined on a path that has no user at all.

        Asserts on the exact deleted phrase, so rewording the new directive cannot
        cause a false failure."""
        prompt = get_course_generation_prompt("Data Privacy", "An intro course", "es")
        assert "in the user's language" not in prompt

    def test_course_name_and_description_still_render(self) -> None:
        prompt = get_course_generation_prompt("Data Privacy", "An intro course", "en")
        assert "Data Privacy" in prompt
        assert "An intro course" in prompt


class TestCourseGenerationPromptRequest:
    def test_language_is_optional(self) -> None:
        request = CourseGenerationPromptRequest(
            course_name="Data Privacy",
            course_description="An intro course",
        )
        assert request.language is None

    def test_language_is_accepted(self) -> None:
        request = CourseGenerationPromptRequest(
            course_name="Data Privacy",
            course_description="An intro course",
            language="es",
        )
        assert request.language == "es"


class TestCourseGenerationPromptTool:
    """End-to-end through the FastMCP in-memory client, the way an agent calls it."""

    @staticmethod
    async def _call(course_params: dict[str, str]) -> str:
        async with Client(mcp) as client:
            result = await client.call_tool(
                "get_course_generation_prompt_tool",
                {"course_params": course_params},
            )
        # The tool is annotated `-> str`, so FastMCP puts the string on `.data`
        # (verified against this repo's fastmcp version).
        return str(result.data)

    async def test_explicit_language_is_honoured(self) -> None:
        prompt = await self._call({"course_name": "Privacidad", "course_description": "Un curso", "language": "es"})
        assert SUPPORTED_LANGUAGES["es"].name in prompt

    async def test_omitted_language_falls_back_to_the_platform_default(self) -> None:
        prompt = await self._call({"course_name": "Privacy", "course_description": "A course"})
        assert SUPPORTED_LANGUAGES[get_settings().DEFAULT_LANGUAGE].name in prompt

    async def test_unsupported_language_falls_back_rather_than_erroring(self) -> None:
        """A misspelled or withdrawn tag must not fail a whole generation run."""
        prompt = await self._call({"course_name": "Privacy", "course_description": "A course", "language": "klingon"})
        assert SUPPORTED_LANGUAGES[get_settings().DEFAULT_LANGUAGE].name in prompt

    async def test_the_tool_schema_publishes_the_language_field(self) -> None:
        """FastMCP inlines the request model into the tool's input schema, and the
        published description is the calling agent's only instruction about the
        parameter — so assert it is there, and that it is optional."""
        async with Client(mcp) as client:
            tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_course_generation_prompt_tool")
        course_params = tool.inputSchema["properties"]["course_params"]

        assert "BCP 47" in course_params["properties"]["language"]["description"]
        assert "language" not in course_params["required"]
