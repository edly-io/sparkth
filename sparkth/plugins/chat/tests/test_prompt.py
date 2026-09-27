from datetime import datetime

from sparkth.plugins.chat.constants import REFUSAL_MESSAGE
from sparkth.plugins.chat.prompt import get_course_design_system_prompt


class TestLearningDesignSystemPrompt:
    def setup_method(self) -> None:
        self.prompt = get_course_design_system_prompt()

    def test_response_boundaries_section_present(self) -> None:
        """Named for what it is: a fallback and response rules, not a second classifier."""
        assert "RESPONSE BOUNDARIES" in self.prompt
        assert "SCOPE & GUARDRAILS" not in self.prompt

    def test_scope_taxonomy_lives_in_the_classifier(self) -> None:
        """The in/out-of-scope lists and their worked examples belong to the scope classifier's
        prompt only; two copies drift, and the classifier's is the one that decides."""
        for duplicate in (
            "Allowed tasks:",
            "Refused tasks",
            "a direct answer to a question you asked",
            "you are now DAN",
            "not even with",
        ):
            assert duplicate not in self.prompt, duplicate

    def test_refusal_fallback_reads_the_whole_conversation(self) -> None:
        """When the classifier fails open this line decides alone; judging the latest message in
        isolation would refuse a one-word answer to the model's own question."""
        assert "whole conversation" in self.prompt

    def test_backstop_guardrails_present(self) -> None:
        """The classifier fails open and never sees document or tool content, so the chat
        model still refuses injection and system-prompt disclosure itself."""
        for rule in ("uploaded documents", "tool results", "system prompt", "partially"):
            assert rule in self.prompt, rule

    def test_refusal_is_only_for_unrelated_requests(self) -> None:
        """Course work the model can't do, and questions about the assistant, get a real
        answer; the refusal sentence would not make sense as a reply to either."""
        for rule in ("only for requests unrelated to course work", "what you can do"):
            assert rule in self.prompt, rule

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
        assert "Write in the user's language" not in get_course_design_system_prompt()

    def test_directive_covers_content_not_just_replies(self) -> None:
        prompt = get_course_design_system_prompt()
        for part in ("assessment questions", "answer options", "feedback"):
            assert part in prompt

    def test_refusal_sentence_is_not_carved_out_of_the_directive(self) -> None:
        """The refusal follows the conversation like everything else the model writes,
        so no exception may re-appear telling the model to reproduce it verbatim."""
        prompt = get_course_design_system_prompt()
        assert "reproduce it exactly as given" not in prompt
