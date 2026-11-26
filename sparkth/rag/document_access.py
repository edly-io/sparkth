"""Which documents RAG may read for the running request.

RAG reads only a document the requesting user owns. A caller can narrow that further to a set of
documents, such as those attached to a conversation. Unbound, every document the user owns is
readable.
"""

from collections.abc import Iterable
from contextvars import ContextVar

from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.auth import current_user_id
from sparkth.lib.documents import Document, get_document

_readable_document_ids: ContextVar[frozenset[int] | None] = ContextVar("readable_document_ids", default=None)


def bind_readable_document_ids(document_ids: Iterable[int]) -> None:
    """Limit RAG to reading ``document_ids`` for the rest of this context.

    Set inside the request's own context, like the requesting user: tasks the request spawns
    copy it, and the next request starts unbound.
    """
    _readable_document_ids.set(frozenset(document_ids))


async def get_readable_document(session: AsyncSession, document_id: int) -> Document | None:
    """Return the document if the requesting user owns it, it is not deleted, and it is one of the
    readable documents when they are bound; else None, so any other document reads as missing."""
    readable = _readable_document_ids.get()
    if readable is not None and document_id not in readable:
        return None
    return await get_document(session, document_id, current_user_id())
