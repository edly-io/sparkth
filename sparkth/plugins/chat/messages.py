"""Reading what a client sent out of a list of chat messages.

A turn arrives either as a plain string or as content blocks — text beside an uploaded document,
or a reference to one already ingested — so nothing downstream can assume where the words are.
Reading the question back out is needed before scope is judged, before retrieval is considered,
and again when the messages are reassembled, which is why it lives here and not under any one of
those.
"""

from sparkth.plugins.chat.schemas import ChatMessage


def get_last_user_text(messages: list[ChatMessage]) -> str:
    """Return the text of the most recent user message, or "" if none of them carry any.

    Falls back to earlier user turns: a turn can be an upload with no words, and the question it
    belongs to is then the one before it. The counterpart is ``get_first_user_text``, which reads
    from the other end to title a conversation.
    """
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
