"""Compose plugin exceptions."""


class ConversationNotFound(Exception):
    """Raised when no conversation has the given UUID."""


class UploadedFilesTooLarge(Exception):
    """Raised when a turn's files would take a conversation's uploaded files over the size it may keep."""


class ConversationBusy(Exception):
    """Raised when a turn is sent to a conversation that is still running another turn."""


class DocumentNotFound(Exception):
    """Raised when a document does not exist, is deleted, or belongs to another user.

    One exception for all three: telling a caller a document exists but is not theirs would
    confirm it to someone who cannot see it.
    """
