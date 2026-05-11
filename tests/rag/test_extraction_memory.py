"""Tests for memory efficiency in PDF extraction.

The batched extraction calls fitz.TOOLS.store_shrink(100) once per batch
to release MuPDF's font/image cache. These tests verify the call pattern
and that it still fires when extraction fails partway through.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.rag.extraction import _extract_pdf


def _make_mock_doc(page_count: int) -> MagicMock:
    doc = MagicMock()
    doc.__enter__ = MagicMock(return_value=doc)
    doc.__exit__ = MagicMock(return_value=False)
    doc.__len__ = MagicMock(return_value=page_count)
    page = MagicMock()
    page.get_text = MagicMock(return_value="lorem ipsum " * 50)  # well above scanned threshold
    doc.__getitem__ = MagicMock(return_value=page)
    return doc


class TestExtractionMemory:
    def test_store_shrunk_after_single_batch(self) -> None:
        """A small doc that fits in one batch shrinks the store once in-loop + once in finally."""
        with (
            patch("app.rag.extraction.fitz.open", return_value=_make_mock_doc(3)),
            patch("app.rag.extraction.fitz.TOOLS") as mock_tools,
            patch("app.rag.extraction.pymupdf4llm.to_markdown", return_value="md"),
        ):
            _extract_pdf(b"%PDF-1.4\n", "small.pdf", batch_size=10)

        # 1 batch in-loop call + 1 finally cleanup call
        assert mock_tools.store_shrink.call_count == 2
        mock_tools.store_shrink.assert_called_with(100)

    def test_store_shrunk_once_per_batch(self) -> None:
        """A doc that spans multiple batches shrinks the store once per batch (plus finally)."""
        with (
            patch("app.rag.extraction.fitz.open", return_value=_make_mock_doc(25)),
            patch("app.rag.extraction.fitz.TOOLS") as mock_tools,
            patch("app.rag.extraction.pymupdf4llm.to_markdown", return_value="md"),
        ):
            _extract_pdf(b"%PDF-1.4\n", "big.pdf", batch_size=10)

        # 25 pages / 10 per batch = 3 batches; +1 finally cleanup
        assert mock_tools.store_shrink.call_count == 4
        mock_tools.store_shrink.assert_called_with(100)

    def test_store_shrunk_even_on_extraction_error(self) -> None:
        """If pymupdf4llm raises mid-batch, the finally block still shrinks the store."""
        with (
            patch("app.rag.extraction.fitz.open", return_value=_make_mock_doc(5)),
            patch("app.rag.extraction.fitz.TOOLS") as mock_tools,
            patch(
                "app.rag.extraction.pymupdf4llm.to_markdown",
                side_effect=RuntimeError("PDF parsing failed"),
            ),
        ):
            with pytest.raises(RuntimeError):
                _extract_pdf(b"%PDF-1.4\n", "bad.pdf", batch_size=10)

        mock_tools.store_shrink.assert_called_with(100)
        assert mock_tools.store_shrink.call_count >= 1
