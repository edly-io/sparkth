"""Chat plugin exceptions."""


class RAGIntentRouterError(Exception):
    """Raised when the router's LLM call fails."""


class ClassifierError(Exception):
    """Raised when a classifier's model call fails, or its answer does not fit the output schema."""


class ClassifierInputError(Exception):
    """Raised when a payload does not satisfy a classifier's declared input schema.

    Deliberately not a ``ClassifierError``: a classifier that falls back on a failed
    classification must not also swallow a malformed call, which is a bug at the call site
    rather than a model that could not decide.
    """
