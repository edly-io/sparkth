"""What a conversation's stored job resolves to."""

import pytest

from sparkth.core.i18n import locale_context
from sparkth.lib.chat.hooks import ChatResponsibility
from sparkth.lib.testing import AddTranslation
from sparkth.plugins.chat.exceptions import ResponsibilityNotEnabled
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
