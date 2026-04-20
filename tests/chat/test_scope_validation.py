"""Tests for query scope validation in chat routes."""


def _is_query_in_scope(query: str) -> bool:
    """Check if a query is related to course creation (in-scope).

    Returns True if the query appears to be about course creation,
    False if it's likely out-of-scope (general knowledge, code, personal advice, etc.).
    """
    if not query:
        return True  # Empty queries default to in-scope (let LLM handle it)

    query_lower = query.lower()

    # In-scope keywords (course creation, instructional design)
    in_scope_keywords = {
        "course",
        "lesson",
        "module",
        "learning",
        "education",
        "training",
        "outline",
        "content",
        "assessment",
        "quiz",
        "exam",
        "evaluation",
        "instructional",
        "pedagogy",
        "pedagogical",
        "curriculum",
        "syllabus",
        "learning objective",
        "learning outcome",
        "ilo",
        "competency",
        "instructional design",
        "course design",
        "elearning",
        "e-learning",
        "teach",
        "teach",
        "student",
        "learner",
        "audience",
    }

    # Out-of-scope keywords (general knowledge, code, personal advice, web search, etc.)
    out_of_scope_keywords = {
        "what is the",
        "who is",
        "when was",
        "where is",
        "how to",
        "tell me",
        "can you help with",
        "can you write",
        "can you code",
        "debug",
        "fix this",
        "what does",
        "explain",
        "summarize",
        "translate",
        "rewrite",
        "python",
        "javascript",
        "java",
        "c++",
        "code",
        "algorithm",
        "algorithm",
        "legal",
        "medical",
        "financial",
        "psychological",
        "advice",
        "weather",
        "news",
        "current events",
        "real-time",
        "poem",
        "poetry",
        "story",
        "creative writing",
        "fiction",
        "capital of",
        "population of",
        "how many",
        "list of",
    }

    # Count in-scope and out-of-scope keyword matches
    in_scope_count = sum(1 for kw in in_scope_keywords if kw in query_lower)
    out_of_scope_count = sum(1 for kw in out_of_scope_keywords if kw in query_lower)

    # If query contains explicit out-of-scope keywords with no in-scope keywords, it's out-of-scope
    if out_of_scope_count > 0 and in_scope_count == 0:
        return False

    # If query contains in-scope keywords, it's in-scope
    if in_scope_count > 0:
        return True

    # Default to in-scope (let LLM decide with system prompt)
    return True


class TestScopeValidation:
    """Test the _is_query_in_scope function."""

    def test_course_creation_queries_are_in_scope(self) -> None:
        """Course creation queries should be in-scope."""
        assert _is_query_in_scope("Create a course on data privacy") is True
        assert _is_query_in_scope("Design a lesson outline for climate change") is True
        assert _is_query_in_scope("What's the best way to structure a course module?") is True
        assert _is_query_in_scope("Create an assessment for my geology course") is True

    def test_general_knowledge_queries_are_out_of_scope(self) -> None:
        """General knowledge queries should be out-of-scope."""
        assert _is_query_in_scope("What is the capital of France?") is False
        assert _is_query_in_scope("What does photosynthesis mean?") is False
        assert _is_query_in_scope("Explain quantum mechanics") is False

    def test_code_help_queries_are_out_of_scope(self) -> None:
        """Code help queries should be out-of-scope."""
        assert _is_query_in_scope("Help me write Python code") is False
        assert _is_query_in_scope("Can you fix this bug?") is False
        assert _is_query_in_scope("Debug my JavaScript code") is False

    def test_personal_advice_queries_are_out_of_scope(self) -> None:
        """Personal advice queries should be out-of-scope."""
        assert _is_query_in_scope("Can you help me with financial advice?") is False
        assert _is_query_in_scope("What's the best legal strategy?") is False

    def test_web_search_queries_are_out_of_scope(self) -> None:
        """Web search and real-time data queries should be out-of-scope."""
        assert _is_query_in_scope("Get me the latest news on the economy") is False
        assert _is_query_in_scope("What is the current weather today?") is False

    def test_teaching_methodology_is_in_scope(self) -> None:
        """Teaching methodology queries should be in-scope."""
        assert _is_query_in_scope("How to teach calculus effectively") is True
        assert _is_query_in_scope("What are best practices for instructional design?") is True

    def test_empty_query_defaults_to_in_scope(self) -> None:
        """Empty queries should default to in-scope (let LLM handle)."""
        assert _is_query_in_scope("") is True

    def test_queries_with_course_keywords_override_defaults(self) -> None:
        """Queries with course keywords should be in-scope even if vague."""
        assert _is_query_in_scope("How many students should I include in my course?") is True
        assert _is_query_in_scope("Can you help create a curriculum on ethics?") is True
