"""What a conversation's stored job decides: its refusal or redirect, and its prompt source."""

import pytest

from sparkth.core.i18n import locale_context
from sparkth.lib.chat.hooks import ChatResponsibility
from sparkth.lib.testing import AddTranslation
from sparkth.plugins.chat.constants import (
    DEFAULT_RESPONSIBILITY,
    REDIRECT_MESSAGE,
    REFUSAL_MESSAGE,
)
from sparkth.plugins.chat.exceptions import ResponsibilityNotEnabled
from sparkth.plugins.chat.models import Conversation
from sparkth.plugins.chat.responsibilities import (
    COURSE_DESIGN,
    refusal_or_redirect,
    stored_responsibility,
)

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


class TestRefusalOrRedirect:
    def test_the_stored_job_proceeds(self) -> None:
        assert refusal_or_redirect(DEFAULT_RESPONSIBILITY, DEFAULT_RESPONSIBILITY) is None

    def test_another_job_is_redirected(self) -> None:
        assert refusal_or_redirect("stub-job", DEFAULT_RESPONSIBILITY) == REDIRECT_MESSAGE

    def test_no_job_is_refused(self) -> None:
        assert refusal_or_redirect(None, DEFAULT_RESPONSIBILITY) == REFUSAL_MESSAGE
