"""The language handling of the MCP course-generation prompt and its tool.

The MCP server has no identity layer, so the language cannot be resolved from a user —
the calling agent supplies it, and anything unusable falls back to the platform default.
"""

import pytest
from fastmcp import Client
from pydantic import ValidationError

from sparkth.lib.language import SUPPORTED_LANGUAGES, language_display_name
from sparkth.lib.settings import get_settings
from sparkth.mcp.prompts.prompt import get_course_generation_prompt
from sparkth.mcp.server import mcp
from sparkth.mcp.types import CourseGenerationPromptRequest


def _other_supported_language_names(excluding_tag: str) -> set[str]:
    """Names of every supported language other than ``excluding_tag``.

    Backs a negative control for the fallback tests: the template's OUTPUT LANGUAGE
    section also carries the brief-mandated, unconditional literal "...not a literal
    translation of English phrasing", so asserting only that the expected language's
    name is present cannot tell the true default apart from some other valid tag
    landing here by mistake. Asserting that none of these names appear catches that.
    """
    return {info.name for tag, info in SUPPORTED_LANGUAGES.items() if tag != excluding_tag}


class TestLanguageFieldBounds:
    """The field is read straight off an unauthenticated MCP request, so its size is the
    caller's choice unless the model bounds it."""

    def test_accepts_a_tag_at_the_ceiling(self) -> None:
        tag = "x" * 35
        assert CourseGenerationPromptRequest(course_name="C", course_description="D", language=tag).language == tag

    def test_rejects_a_tag_past_the_ceiling(self) -> None:
        """35 is the practical ceiling for a registered BCP 47 tag, the same bound
        ``User.language`` carries. Anything longer is not a tag that could ever resolve, so
        it is refused at the boundary rather than carried into the resolver and the log."""
        with pytest.raises(ValidationError):
            CourseGenerationPromptRequest(course_name="C", course_description="D", language="x" * 36)

    def test_still_accepts_an_unusable_but_short_tag(self) -> None:
        """The bound must not turn the documented fallback into a rejection: a short
        nonsense tag is still accepted here and resolved to the default downstream."""
        assert CourseGenerationPromptRequest(course_name="C", course_description="D", language="klingon")


class TestCourseGenerationPromptLanguage:
    @pytest.mark.parametrize(
        ("tag", "expected"),
        [("en", "English"), ("es", "Spanish"), ("de", "German"), ("pt-BR", "Portuguese (Brazil)")],
    )
    def test_names_the_requested_language(self, tag: str, expected: str) -> None:
        """ "de" and "pt-BR" are outside the interface allowlist and must still work —
        before, they raised KeyError."""
        prompt = get_course_generation_prompt("Data Privacy", "An intro course", tag)
        assert expected in prompt

    def test_no_unrendered_placeholder_remains(self) -> None:
        assert "{language_name}" not in get_course_generation_prompt("Data Privacy", "An intro", "de")

    def test_omitted_language_falls_back_to_the_platform_default(self) -> None:
        prompt = get_course_generation_prompt("Data Privacy", "An intro course", None)
        default_name = language_display_name(get_settings().DEFAULT_LANGUAGE)
        assert default_name in prompt

    def test_unusable_tag_falls_back_rather_than_raising(self) -> None:
        """A nonsense tag must not fail an agent-driven generation run."""
        prompt = get_course_generation_prompt("Data Privacy", "An intro course", "klingon")
        assert language_display_name(get_settings().DEFAULT_LANGUAGE) in prompt

    def test_ambiguous_language_instruction_is_gone(self) -> None:
        """ "in the user's language" is undefined on a path that has no user at all.

        Asserts on the exact deleted phrase, so rewording the directive cannot cause a
        false failure."""
        prompt = get_course_generation_prompt("Data Privacy", "An intro course", "es")
        assert "in the user's language" not in prompt

    def test_course_name_and_description_still_render(self) -> None:
        """Nothing here exercises language handling — this guards that the template's
        other placeholders keep rendering, since none of the tests above assert on the
        course text itself."""
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
        default_tag = get_settings().DEFAULT_LANGUAGE
        assert SUPPORTED_LANGUAGES[default_tag].name in prompt

        # Negative control: see _other_supported_language_names for why the
        # positive assertion alone cannot tell the true default from a
        # valid-but-wrong resolution.
        assert not any(name in prompt for name in _other_supported_language_names(default_tag))

    async def test_unsupported_language_falls_back_rather_than_erroring(self) -> None:
        """A misspelled or withdrawn tag must not fail a whole generation run."""
        prompt = await self._call({"course_name": "Privacy", "course_description": "A course", "language": "klingon"})
        default_tag = get_settings().DEFAULT_LANGUAGE
        assert SUPPORTED_LANGUAGES[default_tag].name in prompt

        # Same discrimination gap as above: assert no OTHER supported language's
        # name is present, so a valid-but-wrong fallback resolution is caught.
        assert not any(name in prompt for name in _other_supported_language_names(default_tag))

    async def test_the_tool_schema_publishes_the_language_field(self) -> None:
        """FastMCP inlines the request model into the tool's input schema, and the
        published description is the calling agent's only instruction about the
        parameter — so assert it is there, and that it is optional."""
        async with Client(mcp) as client:
            tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_course_generation_prompt_tool")
        course_params = tool.inputSchema["properties"]["course_params"]
        description = course_params["properties"]["language"]["description"]

        assert "BCP 47" in description
        # Pin the fallback promise itself, not just the "BCP 47" format prefix:
        # this sentence is the calling agent's only instruction that a bad or
        # omitted tag is safe rather than an error.
        assert "the platform default language is used" in description
        assert "language" not in course_params["required"]
