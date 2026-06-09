"""CRUD operations for the Document registry."""

from typing import Optional

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.documents.enums import DocumentStatus
from app.core.documents.models import Document
from app.lib.log import get_logger

logger = get_logger(__name__)


async def create_document(
    session: AsyncSession,
    user_id: int,
    name: str,
    mime_type: Optional[str],
) -> Document:
    """Create a new Document row with QUEUED status and flush (no commit)."""
    doc = Document(user_id=user_id, name=name, mime_type=mime_type)
    session.add(doc)
    await session.flush()
    logger.debug("Registered document id=%d user_id=%d name=%s", doc.id, user_id, name)
    return doc


async def update_document_status(
    session: AsyncSession,
    document_id: int,
    status: DocumentStatus,
    error: Optional[str] = None,
) -> None:
    """Update status (and optional error) on an existing Document. Does not commit."""
    result = await session.exec(select(Document).where(col(Document.id) == document_id))
    doc = result.first()
    if doc is None:
        logger.error("update_document_status: document id=%d not found", document_id)
        return
    doc.status = status
    doc.error = error[:1000] if error and status == DocumentStatus.FAILED else None
    doc.update_timestamp()
    session.add(doc)
    await session.flush()


async def get_document(
    session: AsyncSession,
    document_id: int,
    user_id: int,
) -> Optional[Document]:
    """Return the Document if owned by user_id and not soft-deleted; else None."""
    result = await session.exec(
        select(Document).where(
            col(Document.id) == document_id,
            col(Document.user_id) == user_id,
            col(Document.is_deleted) == False,  # noqa: E712
        )
    )
    return result.first()


async def soft_delete_document(
    session: AsyncSession,
    document_id: int,
) -> None:
    """Soft-delete a Document by id. Does not commit."""
    result = await session.exec(select(Document).where(col(Document.id) == document_id))
    doc = result.first()
    if doc is None:
        return
    doc.soft_delete()
    session.add(doc)
    await session.flush()
