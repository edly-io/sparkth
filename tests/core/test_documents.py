"""Unit tests for the Document model and document service."""

from sqlalchemy import Enum
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.documents.enums import DocumentStatus
from sparkth.core.documents.models import Document
from sparkth.core.documents.service import (
    create_document,
    get_document,
    soft_delete_document,
    update_document_status,
)
from sparkth.lib.documents import list_ready_documents


class TestDocumentModel:
    async def test_default_status_is_queued(self, session: AsyncSession) -> None:
        doc = Document(user_id=1, name="report.pdf", mime_type="application/pdf")
        session.add(doc)
        await session.flush()

        assert doc.id is not None
        assert doc.status == DocumentStatus.QUEUED
        assert doc.error is None
        assert doc.is_deleted is False

    async def test_name_and_mime_stored(self, session: AsyncSession) -> None:
        doc = Document(user_id=1, name="slides.pdf", mime_type="application/vnd.google-apps.presentation")
        session.add(doc)
        await session.flush()

        assert doc.name == "slides.pdf"
        assert doc.mime_type == "application/vnd.google-apps.presentation"

    async def test_mime_type_nullable(self, session: AsyncSession) -> None:
        doc = Document(user_id=1, name="file.txt", mime_type=None)
        session.add(doc)
        await session.flush()

        assert doc.mime_type is None

    def test_status_column_is_native_enum_with_value_labels(self) -> None:
        """documents.status is a native ``documentstatus`` enum whose labels are
        the DocumentStatus *values* (lowercase), matching the rows already stored
        in the column (the SQLite test lane renders the enum as VARCHAR, so only
        this guard catches a label/data mismatch)."""
        column_type = Document.metadata.tables["documents"].columns["status"].type

        assert isinstance(column_type, Enum)
        assert column_type.name == "documentstatus"
        assert column_type.enums == [status.value for status in DocumentStatus]


class TestRegisterDocument:
    async def test_creates_with_queued_status(self, session: AsyncSession) -> None:
        doc = await create_document(session, user_id=1, name="report.pdf", mime_type="application/pdf")
        assert doc.id is not None
        await session.commit()
        await session.refresh(doc)

        assert doc.status == DocumentStatus.QUEUED
        assert doc.name == "report.pdf"

    async def test_mime_type_none_accepted(self, session: AsyncSession) -> None:
        doc = await create_document(session, user_id=1, name="notes.txt", mime_type=None)
        await session.commit()
        await session.refresh(doc)

        assert doc.mime_type is None


class TestUpdateDocumentStatus:
    async def test_sets_status(self, session: AsyncSession) -> None:
        doc = await create_document(session, user_id=1, name="f.pdf", mime_type=None)
        assert doc.id is not None
        document_id = doc.id
        await session.commit()

        await update_document_status(session, document_id, DocumentStatus.READY)
        await session.commit()
        await session.refresh(doc)

        assert doc.status == DocumentStatus.READY
        assert doc.error is None

    async def test_stores_error_on_failed(self, session: AsyncSession) -> None:
        doc = await create_document(session, user_id=1, name="f.pdf", mime_type=None)
        assert doc.id is not None
        document_id = doc.id
        await session.commit()

        await update_document_status(session, document_id, DocumentStatus.FAILED, error="Too large")
        await session.commit()
        await session.refresh(doc)

        assert doc.status == DocumentStatus.FAILED
        assert doc.error == "Too large"


class TestGetDocument:
    async def test_returns_document_for_owner(self, session: AsyncSession) -> None:
        doc = await create_document(session, user_id=1, name="f.pdf", mime_type=None)
        assert doc.id is not None
        document_id = doc.id
        await session.commit()

        found = await get_document(session, document_id, user_id=1)
        assert found is not None
        assert found.id == document_id

    async def test_returns_none_for_wrong_user(self, session: AsyncSession) -> None:
        doc = await create_document(session, user_id=1, name="f.pdf", mime_type=None)
        assert doc.id is not None
        document_id = doc.id
        await session.commit()

        found = await get_document(session, document_id, user_id=999)
        assert found is None

    async def test_returns_none_for_deleted(self, session: AsyncSession) -> None:
        doc = await create_document(session, user_id=1, name="f.pdf", mime_type=None)
        assert doc.id is not None
        document_id = doc.id
        await session.commit()
        await soft_delete_document(session, document_id)
        await session.commit()

        found = await get_document(session, document_id, user_id=1)
        assert found is None


class TestListReadyDocuments:
    async def test_returns_ready_documents_for_user_ordered_by_name_and_id(self, session: AsyncSession) -> None:
        first = Document(user_id=1, name="Beta.pdf", mime_type=None, status=DocumentStatus.READY)
        second = Document(user_id=1, name="Alpha.pdf", mime_type=None, status=DocumentStatus.READY)
        same_name_later = Document(user_id=1, name="Beta.pdf", mime_type=None, status=DocumentStatus.READY)
        queued = Document(user_id=1, name="Queued.pdf", mime_type=None, status=DocumentStatus.QUEUED)
        other_user = Document(user_id=2, name="Other.pdf", mime_type=None, status=DocumentStatus.READY)
        deleted = Document(user_id=1, name="Deleted.pdf", mime_type=None, status=DocumentStatus.READY)
        deleted.soft_delete()
        session.add_all([first, second, same_name_later, queued, other_user, deleted])
        await session.commit()

        documents = await list_ready_documents(session, user_id=1)

        assert [document.name for document in documents] == ["Alpha.pdf", "Beta.pdf", "Beta.pdf"]
        assert [document.id for document in documents] == [second.id, first.id, same_name_later.id]


class TestSoftDeleteDocument:
    async def test_sets_is_deleted(self, session: AsyncSession) -> None:
        doc = await create_document(session, user_id=1, name="f.pdf", mime_type=None)
        assert doc.id is not None
        document_id = doc.id
        await session.commit()

        await soft_delete_document(session, document_id)
        await session.commit()
        await session.refresh(doc)

        assert doc.is_deleted is True
        assert doc.deleted_at is not None
