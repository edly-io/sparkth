"""Tests for RAG cleanup: orphaned chunk deletion (against a real in-memory DB)."""

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.lib.documents import Document
from app.rag.cleanup import cleanup_deleted_documents
from app.rag.models import DocumentChunk, DocumentChunkLink


def _document(doc_id: int, *, is_deleted: bool) -> Document:
    return Document(id=doc_id, user_id=1, name=f"doc-{doc_id}.pdf", is_deleted=is_deleted)


def _chunk(chunk_id: int) -> DocumentChunk:
    return DocumentChunk(id=chunk_id, source_name="src.pdf", content="body")


async def _seed(session: AsyncSession, *objects: object) -> None:
    for obj in objects:
        session.add(obj)
    # cleanup_deleted_documents opens its own session on the shared in-memory
    # connection, so the rows must be committed before it can see them.
    await session.commit()


async def _chunk_ids(session: AsyncSession) -> set[int]:
    session.expire_all()
    return {chunk_id for chunk_id in (await session.exec(select(DocumentChunk.id))).all() if chunk_id is not None}


async def _link_keys(session: AsyncSession) -> set[tuple[int, int]]:
    session.expire_all()
    rows = (await session.exec(select(DocumentChunkLink.document_id, DocumentChunkLink.chunk_id))).all()
    return {(doc_id, chunk_id) for doc_id, chunk_id in rows}


async def _document_ids(session: AsyncSession) -> set[int]:
    session.expire_all()
    return {doc_id for doc_id in (await session.exec(select(Document.id))).all() if doc_id is not None}


class TestCleanupDeletedDocuments:
    async def test_no_deleted_documents_exits_early(self, session: AsyncSession) -> None:
        """With no soft-deleted documents, nothing is touched."""
        await _seed(
            session,
            _document(1, is_deleted=False),
            _chunk(10),
            DocumentChunkLink(document_id=1, chunk_id=10),
        )

        await cleanup_deleted_documents()

        assert await _chunk_ids(session) == {10}
        assert await _link_keys(session) == {(1, 10)}

    async def test_deleted_documents_with_no_chunks(self, session: AsyncSession) -> None:
        """Soft-deleted documents with no linked chunks: documents survive, nothing to clean."""
        await _seed(session, _document(1, is_deleted=True), _document(2, is_deleted=True))

        await cleanup_deleted_documents()

        # Cleanup never hard-deletes Document rows.
        assert await _document_ids(session) == {1, 2}
        assert await _chunk_ids(session) == set()
        assert await _link_keys(session) == set()

    async def test_all_chunks_still_alive_deletes_links_only(self, session: AsyncSession) -> None:
        """Chunks shared with a live document survive; only the deleted doc's links go."""
        await _seed(
            session,
            _document(1, is_deleted=True),
            _document(2, is_deleted=False),
            _chunk(10),
            _chunk(11),
            DocumentChunkLink(document_id=1, chunk_id=10),
            DocumentChunkLink(document_id=1, chunk_id=11),
            DocumentChunkLink(document_id=2, chunk_id=10),
            DocumentChunkLink(document_id=2, chunk_id=11),
        )

        await cleanup_deleted_documents()

        assert await _chunk_ids(session) == {10, 11}
        assert await _link_keys(session) == {(2, 10), (2, 11)}

    async def test_orphaned_chunks_are_deleted(self, session: AsyncSession) -> None:
        """A chunk linked only to deleted documents is removed; a shared one is kept."""
        await _seed(
            session,
            _document(1, is_deleted=True),
            _document(2, is_deleted=False),
            _chunk(10),
            _chunk(11),
            DocumentChunkLink(document_id=1, chunk_id=10),
            DocumentChunkLink(document_id=1, chunk_id=11),
            DocumentChunkLink(document_id=2, chunk_id=10),  # chunk 10 still alive
        )

        await cleanup_deleted_documents()

        assert await _chunk_ids(session) == {10}
        assert await _link_keys(session) == {(2, 10)}

    async def test_all_chunks_orphaned_when_no_alive_documents(self, session: AsyncSession) -> None:
        await _seed(
            session,
            _document(1, is_deleted=True),
            _document(2, is_deleted=True),
            _chunk(10),
            _chunk(11),
            _chunk(12),
            DocumentChunkLink(document_id=1, chunk_id=10),
            DocumentChunkLink(document_id=1, chunk_id=11),
            DocumentChunkLink(document_id=2, chunk_id=12),
        )

        await cleanup_deleted_documents()

        assert await _chunk_ids(session) == set()
        assert await _link_keys(session) == set()

    async def test_shared_chunk_preserved_when_one_document_alive(self, session: AsyncSession) -> None:
        """A chunk linked to both a deleted and a live document must not be deleted."""
        await _seed(
            session,
            _document(1, is_deleted=True),
            _document(2, is_deleted=False),
            _chunk(99),
            DocumentChunkLink(document_id=1, chunk_id=99),
            DocumentChunkLink(document_id=2, chunk_id=99),
        )

        await cleanup_deleted_documents()

        assert await _chunk_ids(session) == {99}
        assert await _link_keys(session) == {(2, 99)}

    async def test_deletes_target_the_right_ids(self, session: AsyncSession) -> None:
        """Only the soft-deleted document's links and its orphaned chunks are removed."""
        await _seed(
            session,
            _document(5, is_deleted=True),
            _document(6, is_deleted=False),
            _chunk(20),
            _chunk(21),
            DocumentChunkLink(document_id=5, chunk_id=20),
            DocumentChunkLink(document_id=5, chunk_id=21),
            DocumentChunkLink(document_id=6, chunk_id=20),  # chunk 20 still alive
        )

        await cleanup_deleted_documents()

        assert await _chunk_ids(session) == {20}  # chunk 21 orphaned and deleted
        assert await _link_keys(session) == {(6, 20)}  # doc 5's links gone
        assert await _document_ids(session) == {5, 6}
