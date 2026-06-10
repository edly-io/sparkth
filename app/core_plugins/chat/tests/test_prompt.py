from app.core_plugins.chat.prompt import REFUSAL_MESSAGE, get_learning_design_system_prompt


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
