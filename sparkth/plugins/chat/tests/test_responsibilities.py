"""What a conversation's stored job decides: its turn reply, its prompt source, its tools."""

import logging

import pytest

from sparkth.lib.chat.hooks import ChatResponsibility
from sparkth.plugins.chat.constants import (
    DEFAULT_RESPONSIBILITY,
    REDIRECT_MESSAGE,
    REFUSAL_MESSAGE,
    UNKNOWN_TOOL_CATEGORY,
)
from sparkth.plugins.chat.models import Conversation
from sparkth.plugins.chat.responsibilities import COURSE_DESIGN, binds_category, stored_responsibility, turn_reply

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
