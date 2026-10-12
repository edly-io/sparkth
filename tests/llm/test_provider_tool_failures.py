"""How the chat tool loop classifies a call that never reached the tool."""

from typing import Any

from langchain_core.tools import StructuredTool

from sparkth.lib.audit import ToolFailureKind
from sparkth.llm.providers import AnthropicProvider


def _lookup_course_tool() -> StructuredTool:
    async def lookup_course(course_id: int) -> dict[str, Any]:
        """Look up a course."""
        return {"course_id": course_id}

    return StructuredTool.from_function(coroutine=lookup_course, name="lookup_course", description="Look up a course.")


async def test_invalid_arguments_are_a_validation_failure() -> None:
    provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-5")

    _result, failure = await provider._execute_tool("lookup_course", {"course_id": "abc"}, [_lookup_course_tool()])

    assert failure is ToolFailureKind.VALIDATION


async def test_a_tool_name_that_is_not_bound_is_a_validation_failure() -> None:
    provider = AnthropicProvider(api_key="test-key", model="claude-sonnet-5")

    result, failure = await provider._execute_tool("no_such_tool", {}, [_lookup_course_tool()])

    assert failure is ToolFailureKind.VALIDATION
    assert "not found" in result
