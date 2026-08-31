"""Building the message list a completion request sends to the provider.

Three sources feed it: the conversation's stored history, the turns the request itself carried, and
a synthetic turn of document references when retrieval is going to run. The request's turns replace
their stored copies because storage flattens content blocks to text and retrieval needs the blocks.
"""

from typing import Any

from sparkth.lib.documents import Document
from sparkth.lib.llm import BaseChatProvider
from sparkth.plugins.chat.models import Message
from sparkth.plugins.chat.routes.utils.rag_search import resolve_document_blocks
from sparkth.plugins.chat.schemas import ChatCompletionRequest, ChatMessage


def _retrieval_turn(documents: list[Document], query_text: str) -> ChatMessage:
    """One turn holding a reference per attached document, plus the question asked of them.

    The question travels with the references so it survives the replacement retrieval performs —
    the model needs both the passages and what was asked about them.
    """
    blocks: list[dict[str, Any]] = [{"type": "drive_file", "file_id": document.id} for document in documents]
    if query_text:
        blocks.append({"type": "text", "text": query_text})
    return ChatMessage(role="user", content=blocks)


def _as_provider_turns(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    return [{"role": message.role, "content": message.content} for message in messages]


async def assemble_provider_messages(
    request: ChatCompletionRequest,
    db_messages: list[Message],
    attached_documents: list[Document],
    query_text: str,
    rag_search_required: bool,
    provider: BaseChatProvider,
) -> tuple[list[dict[str, Any]], list[ChatMessage] | None]:
    """Return the provider's messages, and the turn left for the stream to resolve.

    The second value is the synthetic retrieval turn when there is one, which the streaming path
    hands to the processor so it can replace the references with retrieved passages as it goes. It
    is ``None`` whenever retrieval is not running, and on the non-streaming path the references are
    already resolved here — there is no stream to do it in.
    """
    current_count = len(request.messages)
    history: list[dict[str, Any]] = (
        [{"role": m.role, "content": m.content} for m in db_messages[:-current_count]]
        if len(db_messages) > current_count
        else []
    )

    retrieval_turn: list[ChatMessage] | None = None
    if rag_search_required and attached_documents:
        retrieval_turn = [_retrieval_turn(attached_documents, query_text)]

    if retrieval_turn is None:
        current = _as_provider_turns(request.messages)
    elif request.stream:
        current = _as_provider_turns(retrieval_turn)
    else:
        current = _as_provider_turns(await resolve_document_blocks(messages=retrieval_turn, llm=provider.create_llm()))

    return history + current, retrieval_turn
