"""Tests for memory efficiency in PDF extraction."""

from unittest.mock import patch

import pytest

from app.rag.extraction import _extract_pdf


class TestExtractionMemory:
    """Tests that MuPDF store is properly shrunk after extraction."""

    def test_mupdf_store_shrunk_after_pdf_extraction(self) -> None:
        """Verify fitz.TOOLS.store_shrink(100) is called after extraction."""
        with (
            patch("app.rag.extraction.fitz.TOOLS") as mock_tools,
            patch("app.rag.extraction.pymupdf4llm.to_markdown") as mock_to_markdown,
        ):
            mock_to_markdown.return_value = "# Test\n\nContent\n-----\nPage 2"

            # Provide minimal valid PDF bytes (just a header; pymupdf4llm is mocked anyway)
            pdf_bytes = b"%PDF-1.4\n1 0 obj\nendobj\n"

            _extract_pdf(pdf_bytes, "test.pdf")

            # Verify store_shrink was called with 100
            mock_tools.store_shrink.assert_called_once_with(100)

    def test_mupdf_store_shrunk_even_on_extraction_error(self) -> None:
        """Verify fitz.TOOLS.store_shrink is called even if extraction fails."""
        with (
            patch("app.rag.extraction.fitz.TOOLS") as mock_tools,
            patch("app.rag.extraction.pymupdf4llm.to_markdown") as mock_to_markdown,
        ):
            # Make to_markdown raise an error
            mock_to_markdown.side_effect = RuntimeError("PDF parsing failed")

            pdf_bytes = b"%PDF-1.4\n"

            # Extraction should raise, but finally should still run
            with pytest.raises(RuntimeError):
                _extract_pdf(pdf_bytes, "bad.pdf")

            # Verify store_shrink was still called
            mock_tools.store_shrink.assert_called_once_with(100)
