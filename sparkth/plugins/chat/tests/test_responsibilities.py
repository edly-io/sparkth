"""What a conversation's stored job decides: its prompt source and its tools."""

import logging
from unittest.mock import MagicMock

import pytest

from sparkth.lib.chat.hooks import ChatResponsibility
from sparkth.plugins.chat.constants import UNKNOWN_TOOL_CATEGORY
from sparkth.plugins.chat.models import Conversation
from sparkth.plugins.chat.responsibilities import COURSE_DESIGN, binds_category, stored_responsibility
from sparkth.plugins.chat.routes.utils import resolve_tools
from sparkth.plugins.chat.schemas import ChatCompletionRequest, ChatMessage

_JOBS = {COURSE_DESIGN.name: COURSE_DESIGN}


def _conversation(responsibility: str | None) -> Conversation:
    return Conversation(user_id=1, provider="openai", model="gpt-4o", responsibility=responsibility)


class TestStoredResponsibility:
    def test_a_row_without_a_job_is_course_design(self) -> None:
        assert stored_responsibility(_conversation(None), _JOBS) == COURSE_DESIGN

    def test_an_enabled_job_is_returned(self, stub_job: ChatResponsibility) -> None:
        jobs = {**_JOBS, stub_job.name: stub_job}

        assert stored_responsibility(_conversation("stub-job"), jobs) is stub_job

    def test_a_job_not_enabled_falls_back_to_course_design(self, caplog: pytest.LogCaptureFixture) -> None:
        """Its plugin may be switched off or removed; its conversations stay usable."""
        with caplog.at_level(logging.WARNING, logger="sparkth.plugins.chat.responsibilities"):
            assert stored_responsibility(_conversation("stub-job"), _JOBS) == COURSE_DESIGN

        assert "stub-job" in caplog.text


class TestBindsCategory:
    def test_a_job_with_categories_binds_only_its_own(self, stub_job: ChatResponsibility) -> None:
        assert binds_category(stub_job, "stub-tools") is True
        assert binds_category(stub_job, "openedx-course") is False

    def test_a_job_without_categories_binds_every_unclaimed_one(self, stub_job: ChatResponsibility) -> None:
        assert binds_category(COURSE_DESIGN, "openedx-course") is True
        assert binds_category(COURSE_DESIGN, "stub-tools") is False

    def test_uncategorised_tools_fall_to_course_design(self, stub_job: ChatResponsibility) -> None:
        assert binds_category(COURSE_DESIGN, UNKNOWN_TOOL_CATEGORY) is True
        assert binds_category(stub_job, UNKNOWN_TOOL_CATEGORY) is False


def _tool(name: str) -> MagicMock:
    tool = MagicMock()
    tool.name = name
    return tool


def _registry() -> MagicMock:
    """Two tools: one in a category only course design binds, one in the stub job's own category."""
    registry = MagicMock()
    tools = [_tool("openedx_create_xblock"), _tool("stub_build")]
    registry.get_all_tools.return_value = tools
    registry.get_tools_by_names.return_value = tools
    registry.category_for.side_effect = {"openedx_create_xblock": "openedx-course", "stub_build": "stub-tools"}.get
    return registry


def _request(tools: str | list[str]) -> ChatCompletionRequest:
    return ChatCompletionRequest(llm_config_id=1, messages=[ChatMessage(role="user", content="hi")], tools=tools)


class TestResolveTools:
    async def test_course_design_never_sees_another_jobs_tools(self, stub_job: ChatResponsibility) -> None:
        tools = await resolve_tools(_request("*"), COURSE_DESIGN, _registry())

        assert [tool.name for tool in tools or []] == ["openedx_create_xblock"]

    async def test_a_job_with_categories_sees_only_its_own(self, stub_job: ChatResponsibility) -> None:
        tools = await resolve_tools(_request("*"), stub_job, _registry())

        assert [tool.name for tool in tools or []] == ["stub_build"]

    async def test_naming_another_jobs_tool_does_not_bind_it(self, stub_job: ChatResponsibility) -> None:
        tools = await resolve_tools(_request(["openedx_create_xblock", "stub_build"]), COURSE_DESIGN, _registry())

        assert [tool.name for tool in tools or []] == ["openedx_create_xblock"]

    async def test_disabled_tools_stay_disabled(self) -> None:
        assert await resolve_tools(_request("none"), COURSE_DESIGN, _registry()) is None
