"""Tests for query scope validation (is_query_in_scope in prompt.py)."""

from app.llm.prompt import is_query_in_scope


class TestScopeValidation:
    """Test the is_query_in_scope function against assets/scope_keywords.json."""

    def test_course_creation_queries_are_in_scope(self) -> None:
        assert is_query_in_scope("Create a course on data privacy") is True
        assert is_query_in_scope("Design a lesson outline for climate change") is True
        assert is_query_in_scope("What's the best way to structure a course module?") is True
        assert is_query_in_scope("Create an assessment for my geology course") is True

    def test_general_knowledge_queries_are_out_of_scope(self) -> None:
        assert is_query_in_scope("What is the capital of France?") is False
        assert is_query_in_scope("Who is the president of the United States?") is False
        assert is_query_in_scope("Where is the Eiffel Tower located?") is False

    def test_code_help_queries_are_out_of_scope(self) -> None:
        assert is_query_in_scope("Help me write Python code") is False
        assert is_query_in_scope("Can you fix this bug?") is False
        assert is_query_in_scope("Debug my JavaScript code") is False

    def test_personal_advice_queries_are_out_of_scope(self) -> None:
        assert is_query_in_scope("Can you help me with financial advice?") is False
        assert is_query_in_scope("What's the best legal strategy?") is False

    def test_web_search_queries_are_out_of_scope(self) -> None:
        assert is_query_in_scope("What is the current weather today?") is False
        assert is_query_in_scope("Get me the latest news on the economy") is False

    def test_teaching_methodology_is_in_scope(self) -> None:
        assert is_query_in_scope("How to teach calculus effectively") is True
        assert is_query_in_scope("What are best practices for instructional design?") is True

    def test_empty_query_defaults_to_in_scope(self) -> None:
        """Empty queries should default to in-scope (let LLM handle)."""
        assert is_query_in_scope("") is True

    def test_queries_with_course_keywords_override_out_of_scope_defaults(self) -> None:
        assert is_query_in_scope("How many students should I include in my course?") is True
        assert is_query_in_scope("Can you help create a curriculum on ethics?") is True

    def test_word_boundary_prevents_substring_collisions(self) -> None:
        """'code' should not match 'barcode'; 'java' should not match 'javascript'."""
        # "barcode" contains "code" as a substring — should NOT be flagged out-of-scope
        # (no in_scope keywords either, so defaults to in-scope for LLM to handle)
        assert is_query_in_scope("Build a barcode reader app") is True
        # "java" as a whole word is out-of-scope; no in_scope keyword present
        assert is_query_in_scope("I need help with Java development") is False

    def test_course_related_query_with_potential_substring_match_is_in_scope(self) -> None:
        """Queries that contain both course keywords and out-of-scope substrings should pass."""
        # "learning objective" (in-scope) wins over partial matches
        assert is_query_in_scope("Write a learning objective for data analysis") is True
        # "curriculum" (in-scope) wins
        assert is_query_in_scope("Who is responsible for curriculum design in K-12?") is True
