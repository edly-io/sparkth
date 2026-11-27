"""Building the message list a completion request sends to the provider.

Four sources feed it: the conversation's stored history, the files uploaded from the computer, the
documents attached to the conversation, and the turns the request itself carried. The request's turns
replace their stored copies because storage flattens content blocks to text. The files and the attached
documents are never stored with the history, so they are added every turn.
"""

from collections.abc import Sequence
from typing import Any

from sparkth.lib.documents import Document
from sparkth.plugins.compose.constants import ATTACHED_DOCUMENTS_HEADING
from sparkth.plugins.compose.models import Message
from sparkth.plugins.compose.schemas import ChatCompletionRequest, UploadedFile


def _build_attached_documents_turn(documents: Sequence[Document]) -> dict[str, Any]:
    """One turn listing ``documents`` by id and name, for the planner and its agents to name them by."""
    listed = "\n".join(f"- {document.id}: {document.name}" for document in documents)
    return {"role": "user", "content": f"{ATTACHED_DOCUMENTS_HEADING}\n{listed}"}


def assemble_provider_messages(
    request: ChatCompletionRequest,
    db_messages: list[Message],
    uploaded_files: list[UploadedFile],
    listed_documents: Sequence[Document],
) -> list[dict[str, Any]]:
    """Return the provider's messages.

    ``listed_documents`` are the documents attached to the conversation, ready or not but not deleted,
    listed by id and name before the request's turns when there are any.
    """
    current_count = len(request.messages)
    history: list[dict[str, Any]] = (
        [{"role": m.role, "content": m.content} for m in db_messages[:-current_count]]
        if len(db_messages) > current_count
        else []
    )
    current = [{"role": message.role, "content": message.content} for message in request.messages]
    uploaded_file_messages = [
        {"role": "user", "content": f"[File: {file.name}]\n\n{file.text}"} for file in uploaded_files
    ]
    listing = [_build_attached_documents_turn(listed_documents)] if listed_documents else []
    return history + uploaded_file_messages + listing + current
