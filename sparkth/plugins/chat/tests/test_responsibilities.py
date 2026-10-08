"""What a conversation's stored job decides: its turn reply, its prompt source, its tools."""

from unittest.mock import MagicMock

import pytest

from sparkth.core.i18n import locale_context
from sparkth.lib.chat.hooks import ChatResponsibility
from sparkth.lib.testing import AddTranslation
from sparkth.plugins.chat.constants import (
    DEFAULT_RESPONSIBILITY,
    REDIRECT_MESSAGE,
    REFUSAL_MESSAGE,
    UNKNOWN_TOOL_CATEGORY,
)
from sparkth.plugins.chat.exceptions import ResponsibilityNotEnabled
from sparkth.plugins.chat.models import Conversation
from sparkth.plugins.chat.responsibilities import COURSE_DESIGN, binds_category, stored_responsibility, turn_reply
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

    def test_a_job_whose_plugin_is_switched_off_is_refused_by_its_label(
        self, stub_job: ChatResponsibility, translation_catalog: AddTranslation
    ) -> None:
        """The author is told which job the conversation is for, in their language."""
        translation_catalog(stub_job.label, "Trabajo stub")

        with locale_context("es"), pytest.raises(ResponsibilityNotEnabled) as raised:
            stored_responsibility(_conversation("stub-job"), _JOBS)

        assert "Trabajo stub" in str(raised.value)

    def test_a_job_no_plugin_registers_is_refused_by_its_stored_name(self) -> None:
        with pytest.raises(ResponsibilityNotEnabled) as raised:
            stored_responsibility(_conversation("gone-job"), _JOBS)

        assert "gone-job" in str(raised.value)


class TestTurnReply:
    def test_the_stored_job_proceeds(self) -> None:
        assert turn_reply(DEFAULT_RESPONSIBILITY, DEFAULT_RESPONSIBILITY) is None

    def test_another_job_is_redirected(self) -> None:
        assert turn_reply("stub-job", DEFAULT_RESPONSIBILITY) == REDIRECT_MESSAGE

    def test_no_job_is_refused(self) -> None:
        assert turn_reply(None, DEFAULT_RESPONSIBILITY) == REFUSAL_MESSAGE


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
