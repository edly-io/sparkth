"""Chat plugin exceptions."""


class RAGSearchError(Exception):
    """Raised when the search classifier cannot decide whether to retrieve."""


class ClassifierError(Exception):
    """Raised when a classifier's model call fails, or its answer does not fit the output schema."""
