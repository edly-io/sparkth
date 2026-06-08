"""Unit tests for the Document model."""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.documents.enums import DocumentStatus
from app.core.documents.models import Document


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
