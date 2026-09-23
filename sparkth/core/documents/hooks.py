"""Lifecycle hooks a plugin can hang off the document registry.

A plugin cannot be imported from core, so a plugin holding rows that reference a
document has no way to learn the document went away. It registers a handler here
instead.
"""

from collections.abc import Awaitable, Callable

from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.documents.models import Document
from sparkth.lib.hooks import PluginCollectionHook

DocumentDeletedHandler = Callable[[AsyncSession, Document], Awaitable[None]]

# Notified by `soft_delete_document` once the document is flagged, inside the caller's
# still-open transaction
DOCUMENT_DELETED: PluginCollectionHook[DocumentDeletedHandler] = PluginCollectionHook()


async def notify_document_deleted(session: AsyncSession, document: Document) -> None:
    """Run every registered handler against the document being deleted."""
    for _plugin, handler in DOCUMENT_DELETED.iter_items():
        await handler(session, document)
