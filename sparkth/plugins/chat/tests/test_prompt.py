from datetime import datetime

from sparkth.lib.chat.hooks import ChatResponsibility
from sparkth.plugins.chat.constants import REFUSAL_MESSAGE
from sparkth.plugins.chat.prompt import render_system_prompt
from sparkth.plugins.chat.responsibilities import COURSE_DESIGN

_STUB = ChatResponsibility("stub-job", "Stub job", "Stub section", "Stub scope.", "Stub section body.", frozenset())


class TestRenderSystemPrompt:
    def test_todays_date_is_substituted(self) -> None:
        prompt = render_system_prompt([COURSE_DESIGN])

        assert "{current_datetime}" not in prompt
        assert str(datetime.now().year) in prompt

    def test_the_refusal_sentence_is_included(self) -> None:
        """Locale independence is guarded by test_refusal_language.TestRefusalInTheSystemPrompt."""
        assert REFUSAL_MESSAGE in render_system_prompt([COURSE_DESIGN])

    def test_each_section_is_rendered_under_its_title(self) -> None:
        prompt = render_system_prompt([COURSE_DESIGN, _STUB])

        assert f"## {COURSE_DESIGN.title}\n{COURSE_DESIGN.prompt}" in prompt
        assert "## Stub section\nStub section body." in prompt

    def test_only_the_given_sections_are_rendered(self) -> None:
        assert "## Stub section" not in render_system_prompt([COURSE_DESIGN])

    def test_a_section_is_inserted_without_formatting(self) -> None:
        """A section may carry JSON or code examples; its braces reach the model as written."""
        braced = ChatResponsibility("b", "B", "Braced", "Scope.", 'Return {"id": 1} and {unknown}.', frozenset())

        assert 'Return {"id": 1} and {unknown}.' in render_system_prompt([braced])

    def test_no_skeleton_placeholder_is_left(self) -> None:
        prompt = render_system_prompt([COURSE_DESIGN])

        for placeholder in ("{refusal_message}", "{capabilities}"):
            assert placeholder not in prompt
