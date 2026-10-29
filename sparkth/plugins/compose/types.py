"""Value objects the compose service returns.

These carry what a service call did, separate from the SQLModel rows in
:mod:`sparkth.plugins.compose.models` and the request/response bodies in
:mod:`sparkth.plugins.compose.schemas`.
"""

from dataclasses import dataclass

from sparkth.lib.documents import Document
from sparkth.plugins.compose.models import ConversationAttachment


@dataclass(frozen=True)
class AttachOutcome:
    """What one request's ``document_ids`` did.

    ``created`` holds only the attachments this call wrote: attaching is upsert-safe, so a
    document already in play is not a new action.
    """

    created: list[ConversationAttachment]
    requested_count: int
    skipped_count: int


@dataclass(frozen=True)
class ConversationDocuments:
    """A conversation's attachments, split by whether chat can actually read them."""

    ready: list[Document]
    unusable: list[Document]
