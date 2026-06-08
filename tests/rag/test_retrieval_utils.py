"""Tests for RAG retrieval utils — _lookup_document and validate_files_ready."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.documents.enums import DocumentStatus
from app.rag.exceptions import DocumentNotFoundError, RAGNotReadyError
from app.rag.retrieval.utils import _lookup_document, validate_files_ready


def _make_session() -> AsyncMock:
    session = AsyncMock()
    session.exec = AsyncMock()
    return session


def _make_doc(doc_id: int, user_id: int, status: DocumentStatus, is_deleted: bool = False) -> MagicMock:
    doc = MagicMock()
    doc.id = doc_id
    doc.user_id = user_id
    doc.status = status
    doc.is_deleted = is_deleted
    return doc


class TestLookupDocument:
    async def test_returns_ready_document(self) -> None:
        doc = _make_doc(1, 1, DocumentStatus.READY)
        session = _make_session()
        result_mock = MagicMock()
        result_mock.first.return_value = doc
        session.exec.return_value = result_mock

        found = await _lookup_document(session, 1, 1)
        assert found is doc

    async def test_raises_not_found_when_missing(self) -> None:
        session = _make_session()
        result_mock = MagicMock()
        result_mock.first.return_value = None
        session.exec.return_value = result_mock

        with pytest.raises(DocumentNotFoundError):
            await _lookup_document(session, 1, 99)

    async def test_raises_not_ready_when_processing(self) -> None:
        doc = _make_doc(1, 1, DocumentStatus.PROCESSING)
        session = _make_session()
        result_mock = MagicMock()
        result_mock.first.return_value = doc
        session.exec.return_value = result_mock

        with pytest.raises(RAGNotReadyError):
            await _lookup_document(session, 1, 1)

    async def test_raises_not_ready_when_queued(self) -> None:
        doc = _make_doc(1, 1, DocumentStatus.QUEUED)
        session = _make_session()
        result_mock = MagicMock()
        result_mock.first.return_value = doc
        session.exec.return_value = result_mock

        with pytest.raises(RAGNotReadyError):
            await _lookup_document(session, 1, 1)


class TestValidateFilesReady:
    async def test_passes_when_all_ready(self) -> None:
        docs = [_make_doc(1, 1, DocumentStatus.READY), _make_doc(2, 1, DocumentStatus.READY)]
        session = _make_session()
        result_mock = MagicMock()
        result_mock.all.return_value = docs
        session.exec.return_value = result_mock

        await validate_files_ready(session, 1, [1, 2])

    async def test_raises_not_found_for_missing_id(self) -> None:
        session = _make_session()
        result_mock = MagicMock()
        result_mock.all.return_value = []
        session.exec.return_value = result_mock

        with pytest.raises(DocumentNotFoundError):
            await validate_files_ready(session, 1, [99])

    async def test_raises_not_ready_for_non_ready_doc(self) -> None:
        doc = _make_doc(1, 1, DocumentStatus.PROCESSING)
        session = _make_session()
        result_mock = MagicMock()
        result_mock.all.return_value = [doc]
        session.exec.return_value = result_mock

        with pytest.raises(RAGNotReadyError):
            await validate_files_ready(session, 1, [1])
