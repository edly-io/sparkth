"""What a conversation's stored job resolves to."""

import logging

import pytest

from sparkth.lib.chat.hooks import ChatResponsibility
from sparkth.plugins.chat.models import Conversation
from sparkth.plugins.chat.responsibilities import COURSE_DESIGN, stored_responsibility

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
