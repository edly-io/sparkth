"""Unit tests for the Document model and document service."""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.documents.enums import DocumentStatus
from app.core.documents.models import Document
from app.core.documents.service import (
    create_document,
    get_document,
    soft_delete_document,
    update_document_status,
)


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


class TestRegisterDocument:
    async def test_creates_with_queued_status(self, session: AsyncSession) -> None:
        doc = await create_document(session, user_id=1, name="report.pdf", mime_type="application/pdf")
        await session.commit()

        assert doc.id is not None
        assert doc.status == DocumentStatus.QUEUED
        assert doc.name == "report.pdf"

    async def test_mime_type_none_accepted(self, session: AsyncSession) -> None:
        doc = await create_document(session, user_id=1, name="notes.txt", mime_type=None)
        await session.commit()

        assert doc.mime_type is None


class TestUpdateDocumentStatus:
    async def test_sets_status(self, session: AsyncSession) -> None:
        doc = await create_document(session, user_id=1, name="f.pdf", mime_type=None)
        await session.commit()
        assert doc.id is not None

        await update_document_status(session, doc.id, DocumentStatus.READY)
        await session.commit()
        await session.refresh(doc)

        assert doc.status == DocumentStatus.READY
        assert doc.error is None

    async def test_stores_error_on_failed(self, session: AsyncSession) -> None:
        doc = await create_document(session, user_id=1, name="f.pdf", mime_type=None)
        await session.commit()
        assert doc.id is not None

        await update_document_status(session, doc.id, DocumentStatus.FAILED, error="Too large")
        await session.commit()
        await session.refresh(doc)

        assert doc.status == DocumentStatus.FAILED
        assert doc.error == "Too large"


class TestGetDocument:
    async def test_returns_document_for_owner(self, session: AsyncSession) -> None:
        doc = await create_document(session, user_id=1, name="f.pdf", mime_type=None)
        await session.commit()
        assert doc.id is not None

        found = await get_document(session, doc.id, user_id=1)
        assert found is not None
        assert found.id == doc.id

    async def test_returns_none_for_wrong_user(self, session: AsyncSession) -> None:
        doc = await create_document(session, user_id=1, name="f.pdf", mime_type=None)
        await session.commit()
        assert doc.id is not None

        found = await get_document(session, doc.id, user_id=999)
        assert found is None

    async def test_returns_none_for_deleted(self, session: AsyncSession) -> None:
        doc = await create_document(session, user_id=1, name="f.pdf", mime_type=None)
        await session.commit()
        assert doc.id is not None
        await soft_delete_document(session, doc.id)
        await session.commit()

        found = await get_document(session, doc.id, user_id=1)
        assert found is None


class TestSoftDeleteDocument:
    async def test_sets_is_deleted(self, session: AsyncSession) -> None:
        doc = await create_document(session, user_id=1, name="f.pdf", mime_type=None)
        await session.commit()
        assert doc.id is not None

        await soft_delete_document(session, doc.id)
        await session.commit()
        await session.refresh(doc)

        assert doc.is_deleted is True
        assert doc.deleted_at is not None
