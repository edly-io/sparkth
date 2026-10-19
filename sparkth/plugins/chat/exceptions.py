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


class ScopeCheckError(Exception):
    """Raised when the scope classifier cannot judge a turn.

    ``cause`` is the failure underneath: a classifier error, an OpenAI refusal or a provider
    error. The caller words the message the user reads from it.
    """

    def __init__(self, cause: Exception) -> None:
        super().__init__(f"{type(cause).__name__}: {cause}")
        self.cause = cause


class ClassifierError(Exception):
    """Raised when a classifier's LangChain call fails, or its answer does not fit the output schema."""
