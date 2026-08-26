"""Reading what a client sent out of a list of chat messages.

A turn arrives either as a plain string or as content blocks — text beside an uploaded document,
or a reference to one already ingested — so nothing downstream can assume where the words are.
These read one thing each out of that shape and are used by the route and by the stream alike,
which is why they live here rather than under either.
"""

from sparkth.lib.log import get_logger
from sparkth.plugins.chat.schemas import ChatMessage

logger = get_logger(__name__)


def extract_query_text(messages: list[ChatMessage]) -> str:
    """Extract the user's plain text from the last user message for RAG retrieval."""
    for msg in reversed(messages):
        if msg.role != "user":
            continue
        if isinstance(msg.content, str):
            return msg.content.strip()
        text_parts = [
            block.get("text", "") for block in msg.content if isinstance(block, dict) and block.get("type") == "text"
        ]
        joined = " ".join(text_parts).strip()
        if joined:
            return joined
    return ""


def collect_document_ids(messages: list[ChatMessage]) -> list[int]:
    document_ids: list[int] = []
    for msg in messages:
        if not isinstance(msg.content, list):
            continue
        for block in msg.content:
            if not isinstance(block, dict) or block.get("type") != "drive_file":
                continue
            raw_id = block.get("file_id")
            if raw_id is None:
                logger.warning("Skipping document attachment block missing file_id in stream: %s", block)
                continue
            document_ids.append(int(raw_id))
    return document_ids
