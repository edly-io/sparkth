"""Tests for RAG ingestion exception hierarchy."""

from app.rag.exceptions import (
    RAGError,
    RAGIngestionError,
    UnsupportedFileTypeError,
)


class TestIngestionExceptions:
    def test_ingestion_error_is_rag_error(self) -> None:
        assert issubclass(RAGIngestionError, RAGError)

    def test_unsupported_file_type_is_ingestion_error(self) -> None:
        assert issubclass(UnsupportedFileTypeError, RAGIngestionError)

    def test_unsupported_file_type_message(self) -> None:
        exc = UnsupportedFileTypeError("Unsupported file type '.png' for RAG ingestion.")
        assert "png" in str(exc)
