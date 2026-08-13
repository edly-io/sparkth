import pytest

from sparkth.lib.language import SUPPORTED_LANGUAGES
from sparkth.plugins.chat.prompt import REFUSAL_MESSAGE, get_learning_design_system_prompt


class TestLearningDesignSystemPrompt:
    def setup_method(self) -> None:
        self.prompt = get_learning_design_system_prompt("en")

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


class TestSystemPromptLanguage:
    """The prompt must name the output language explicitly, and must no longer
    contain the ambiguous instruction it replaces."""

    @pytest.mark.parametrize("tag", sorted(SUPPORTED_LANGUAGES))
    def test_names_the_language_for_every_supported_tag(self, tag: str) -> None:
        prompt = get_learning_design_system_prompt(tag)
        assert SUPPORTED_LANGUAGES[tag].name in prompt

    @pytest.mark.parametrize("tag", sorted(SUPPORTED_LANGUAGES))
    def test_no_unrendered_placeholder_remains(self, tag: str) -> None:
        assert "{language_name}" not in get_learning_design_system_prompt(tag)

    def test_ambiguous_language_instruction_is_gone(self) -> None:
        """ "Write in the user's language" reads as the language they typed in, which is
        not their configured preference. It must be replaced, not supplemented, or the
        model gets contradictory guidance.

        Asserts on the exact deleted sentence rather than banning the phrase family:
        the new directive legitimately says "regardless of the language the user writes
        to you in", and a broader assertion would fail on a harmless rewording."""
        assert "Write in the user's language" not in get_learning_design_system_prompt("es")

    def test_directive_covers_content_not_just_replies(self) -> None:
        prompt = get_learning_design_system_prompt("es")
        for part in ("assessment questions", "answer options", "feedback"):
            assert part in prompt

    def test_refusal_sentence_is_carved_out_of_the_directive(self) -> None:
        """The template hands the model the refusal sentence and says to send it
        verbatim. Without an explicit exception the language directive contradicts
        that, and the model's refusal drifts from the deterministic streamed one."""
        prompt = get_learning_design_system_prompt("es")
        assert "reproduce it exactly as given" in prompt
