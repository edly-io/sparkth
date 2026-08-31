"""Chat plugin exceptions."""


class RAGIntentRouterError(Exception):
    """Raised when the router's LLM call fails."""


class ClassifierError(Exception):
    """Raised when a classifier's model call fails, or its answer does not fit the output schema."""
