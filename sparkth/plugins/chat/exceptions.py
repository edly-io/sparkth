"""Chat plugin exceptions."""


class ConversationNotFound(Exception):
    """Raised when a conversation UUID does not resolve to one the caller owns."""


class DocumentNotFound(Exception):
    """Raised when a document does not exist, is deleted, or belongs to another user.

    One exception for all three: telling a caller a document exists but is not theirs would
    confirm it to someone who cannot see it.
    """


class RAGSearchError(Exception):
    """Raised when the search classifier cannot decide whether to retrieve."""


class ClassifierError(Exception):
    """Raised when a classifier's model call fails, or its answer does not fit the output schema."""
