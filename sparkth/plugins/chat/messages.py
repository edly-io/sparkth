"""Reading what a client sent out of a list of chat messages.

A turn arrives either as a plain string or as content blocks — text beside an uploaded document,
or a reference to one already ingested — so nothing downstream can assume where the words are.
One place decides where the words are; the readers below differ only in which end of the
conversation they start from and what they return when there are none.
"""

from sparkth.plugins.chat.schemas import ChatMessage


def text_of(message: ChatMessage) -> str:
    """Return a message's text, or "" if it carries none.

    Content blocks that are not text — an uploaded document, an image — contribute nothing: a
    turn can consist entirely of them, which is what makes the empty return a real case rather
    than a guard.
    """
    if not isinstance(message.content, list):
        return message.content.strip()
    parts = [
        block.get("text", "") for block in message.content if isinstance(block, dict) and block.get("type") == "text"
    ]
    return " ".join(parts).strip()


def get_last_user_text(messages: list[ChatMessage]) -> str:
    """Return the text of the most recent user message, or "" if none of them carry any.

    Falls back to earlier user turns: a turn can be an upload with no words, and the question it
    belongs to is then the one before it.
    """
    for message in reversed(messages):
        if message.role != "user":
            continue
        if text := text_of(message):
            return text
    return ""


def get_first_user_text(messages: list[ChatMessage]) -> str | None:
    """Return the text of the first user message that has any, else None.

    Reads from the opposite end to ``get_last_user_text`` because it answers a different
    question: what the conversation was opened about, which is what titles it.
    """
    for message in messages:
        if message.role != "user":
            continue
        if text := text_of(message):
            return text
    return None
