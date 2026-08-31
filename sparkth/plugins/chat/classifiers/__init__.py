"""The chat plugin's classifiers, exported so callers import them from the package."""

from sparkth.plugins.chat.classifiers.message_scope import MessageScopeClassifier
from sparkth.plugins.chat.classifiers.rag_search import RAGSearchClassifier

# Explicit, or mypy reads the imports as implicit re-exports and flags them.
__all__ = ["MessageScopeClassifier", "RAGSearchClassifier"]
