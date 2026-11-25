from datetime import datetime

from sparkth.lib.compose.hooks import Agent
from sparkth.plugins.compose.constants import REFUSAL_MESSAGE
from sparkth.plugins.compose.prompt import render_system_prompt
from sparkth.plugins.compose.tests.conftest import STUB_AGENT

LMS_HEADING = "Publishing and managing courses on your LMS"


class TestRenderSystemPrompt:
    def test_todays_date_is_substituted(self) -> None:
        prompt = render_system_prompt(STUB_AGENT)

        assert "{current_datetime}" not in prompt
        assert str(datetime.now().year) in prompt

    def test_the_refusal_sentence_is_included(self) -> None:
        """Locale independence is guarded by test_refusal_language.TestRefusalInTheSystemPrompt."""
        assert REFUSAL_MESSAGE in render_system_prompt(STUB_AGENT)

    def test_only_the_given_agents_section_is_rendered(self) -> None:
        assert "## Other agent" not in render_system_prompt(STUB_AGENT)

    def test_a_section_is_inserted_without_formatting(self) -> None:
        """A section may carry JSON or code examples; its braces reach the model as written."""
        braced = Agent("braced", "Braced", "Scope.", 'Return {"id": 1} and {unknown}.', "Bracing…")

        assert 'Return {"id": 1} and {unknown}.' in render_system_prompt(braced)

    def test_no_skeleton_placeholder_is_left(self) -> None:
        prompt = render_system_prompt(STUB_AGENT)

        for placeholder in ("{refusal_message}", "{work}"):
            assert placeholder not in prompt

    def test_the_agents_section_comes_under_its_work(self) -> None:
        assert f"YOUR WORK\n\n## {STUB_AGENT.title}\n{STUB_AGENT.prompt}" in render_system_prompt(STUB_AGENT)

    def test_an_agent_is_not_told_to_choose_between_kinds_of_work(self) -> None:
        """The planner picks the agent and splits a request across agents; an agent holds only its own work."""
        prompt = render_system_prompt(STUB_AGENT)

        assert "capabilit" not in prompt.lower()


class TestWhatTheAuthorIsNeverShown:
    def test_no_agent_may_show_how_it_works_even_when_the_author_asks(self) -> None:
        prompt = render_system_prompt(STUB_AGENT)

        assert "unless the author asks" not in prompt
        assert "even when the author asks" in prompt

    def test_every_agent_is_told_how_to_speak_of_a_failure(self) -> None:
        assert "Never show or quote an error message" in render_system_prompt(STUB_AGENT)


class TestLmsOperations:
    def test_no_agent_is_told_it_runs_lms_operations(self) -> None:
        assert LMS_HEADING not in render_system_prompt(STUB_AGENT)
