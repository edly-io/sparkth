"""Tests for RAG ingestion exception hierarchy."""

from app.rag.exceptions import (
    FileTypeNotAllowedError,
    RAGError,
    RAGIngestionError,
    UnsupportedFileTypeError,
)


class TestIngestionExceptions:
    def test_ingestion_error_is_rag_error(self) -> None:
        assert issubclass(RAGIngestionError, RAGError)

    def test_unsupported_file_type_is_ingestion_error(self) -> None:
        assert issubclass(UnsupportedFileTypeError, RAGIngestionError)

    def test_file_type_not_allowed_is_ingestion_error(self) -> None:
        assert issubclass(FileTypeNotAllowedError, RAGIngestionError)

    def test_file_type_not_allowed_builds_message_from_allowed_list(self) -> None:
        exc = FileTypeNotAllowedError(["pdf", "txt"])
        assert exc.allowed_extensions == ["pdf", "txt"]
        assert str(exc) == "Unsupported file extension. Allowed: .pdf, .txt."

    def test_unsupported_file_type_message(self) -> None:
        exc = UnsupportedFileTypeError("Unsupported file type '.png' for RAG ingestion.")
        assert "png" in str(exc)
