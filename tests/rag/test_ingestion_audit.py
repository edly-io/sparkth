"""Audit capture for RAG ingestion.

Every ``ingest_document`` call must leave an audit record of the target
document and outcome: content entering the retrieval corpus (or failing to)
is never silent.
"""

from unittest.mock import MagicMock, patch

import pytest

from sparkth.lib.audit.events import RAGDocumentIngestedAuditEvent
from sparkth.lib.audit.hooks import AUDIT_EVENTS
from sparkth.lib.rag import ScannedPDFError, UnsupportedFileTypeError, ingest_document
from sparkth.lib.testing import AuditEventsFetcher


def test_ingested_event_type_is_registered() -> None:
    assert AUDIT_EVENTS.resolve("rag.document_ingested") is RAGDocumentIngestedAuditEvent


class TestIngestionAudit:
    async def test_successful_ingestion_records_success_event(self, audit_events: AuditEventsFetcher) -> None:
        extraction = MagicMock(markdown="# H\ntext")
        chunker = MagicMock()
        chunker.return_value.chunk.return_value = [MagicMock()]
        with (
            patch("sparkth.rag.ingestion.extract_to_markdown", return_value=extraction),
            patch("sparkth.rag.ingestion.DocumentChunker", chunker),
            patch("sparkth.rag.ingestion.store_and_link_chunks", return_value=(2, 1)),
        ):
            await ingest_document("a.txt", b"x", 10)

        (event,) = await audit_events()
        assert (event.category, event.action) == ("rag", "document_ingested")
        assert event.outcome == "success"
        assert event.target_type == "document"
        assert event.target_id == "10"
        assert event.new_values == {"filename": "a.txt", "new_chunks": 2, "reused_chunks": 1}

    async def test_empty_extraction_still_records_success(self, audit_events: AuditEventsFetcher) -> None:
        """A document that yields no chunks still entered the pipeline; the
        zero-chunk outcome is part of the trail."""
        extraction = MagicMock(markdown="")
        chunker = MagicMock()
        chunker.return_value.chunk.return_value = []
        with (
            patch("sparkth.rag.ingestion.extract_to_markdown", return_value=extraction),
            patch("sparkth.rag.ingestion.DocumentChunker", chunker),
        ):
            await ingest_document("a.txt", b"x", 10)

        (event,) = await audit_events()
        assert event.outcome == "success"
        assert event.new_values == {"filename": "a.txt", "new_chunks": 0, "reused_chunks": 0}

    async def test_unsupported_file_type_records_failure(self, audit_events: AuditEventsFetcher) -> None:
        with pytest.raises(UnsupportedFileTypeError):
            await ingest_document("img.png", b"x", 10)

        (event,) = await audit_events()
        assert (event.category, event.action) == ("rag", "document_ingested")
        assert event.outcome == "failure"
        assert event.target_id == "10"
        assert event.error_detail
        assert event.new_values is None

    async def test_scanned_pdf_records_failure(self, audit_events: AuditEventsFetcher) -> None:
        with patch("sparkth.rag.ingestion.extract_to_markdown", side_effect=ScannedPDFError("a.pdf")):
            with pytest.raises(ScannedPDFError):
                await ingest_document("a.pdf", b"x", 10)

        (event,) = await audit_events()
        assert event.outcome == "failure"
        assert event.error_detail
