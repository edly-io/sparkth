"""Tests for the app.lib.rag public API surface."""

import app.lib.rag as rag_api


class TestRagPublicApi:
    def test_exposes_ingest_document(self) -> None:
        assert callable(rag_api.ingest_document)

    def test_exposes_ingestion_result(self) -> None:
        assert rag_api.IngestionResult(new_chunks=1, reused_chunks=2).new_chunks == 1

    def test_exposes_rag_status(self) -> None:
        assert rag_api.RagStatus.READY is rag_api.RagStatus.READY

    def test_exposes_ingestion_exceptions(self) -> None:
        assert issubclass(rag_api.UnsupportedFileTypeError, Exception)
        assert issubclass(rag_api.FileTypeNotAllowedError, Exception)
        assert issubclass(rag_api.ScannedPDFError, Exception)
