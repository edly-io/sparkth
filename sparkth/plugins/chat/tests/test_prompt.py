from datetime import datetime

from sparkth.plugins.chat.constants import REFUSAL_MESSAGE
from sparkth.plugins.chat.prompt import get_learning_design_system_prompt


class TestLearningDesignSystemPrompt:
    def setup_method(self) -> None:
        self.prompt = get_learning_design_system_prompt()

    def test_scope_and_guardrails_section_present(self) -> None:
        assert "SCOPE & GUARDRAILS" in self.prompt

    def test_allowed_tasks_section_present_and_non_empty(self) -> None:
        assert "Allowed tasks:" in self.prompt
        allowed_index = self.prompt.index("Allowed tasks:")
        # At least one bullet point must follow the heading
        section_after = self.prompt[allowed_index:]
        assert "- " in section_after

    def test_refusal_sentence_present_verbatim(self) -> None:
        assert REFUSAL_MESSAGE in self.prompt

    def test_todays_date_is_substituted(self) -> None:
        """The template opens with the date. An unrendered placeholder tells the model nothing
        and breaks nothing else, so this is the only thing that would catch it."""
        assert "{current_datetime}" not in self.prompt
        assert str(datetime.now().year) in self.prompt


class TestSystemPromptLanguage:
    """The directive states the language rule in full — follow and switch with the
    conversation, cover all content, and no longer contain the ambiguous instruction
    it replaces."""

    def test_ambiguous_language_instruction_is_gone(self) -> None:
        """ "Write in the user's language" is vague about both which language it means
        and how much of the output it covers. The directive states both explicitly.

        Asserts on the exact sentence rather than banning the phrase family: the
        directive legitimately talks about the language the user writes in, and a
        broader assertion would fail on a harmless rewording."""
        assert "Write in the user's language" not in get_learning_design_system_prompt()

    def test_directive_covers_content_not_just_replies(self) -> None:
        prompt = get_learning_design_system_prompt()
        for part in ("assessment questions", "answer options", "feedback"):
            assert part in prompt

    def test_refusal_sentence_is_not_carved_out_of_the_directive(self) -> None:
        """The refusal follows the conversation like everything else the model writes,
        so no exception may re-appear telling the model to reproduce it verbatim."""
        prompt = get_learning_design_system_prompt()
        assert "reproduce it exactly as given" not in prompt
