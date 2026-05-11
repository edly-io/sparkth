"""Tests for scanned/image-only PDF detection in _extract_pdf.

We assert behaviour at two levels:
  * `_is_scanned_pdf` — the page-sampling primitive.
  * `_extract_pdf`    — the integration point that raises ScannedPDFError.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.rag.exceptions import ScannedPDFError
from app.rag.extraction import _extract_pdf, _is_scanned_pdf


def _make_doc(pages_text: list[str]) -> MagicMock:
    """Build a mock fitz.Document where doc[i].get_text("text") returns pages_text[i]."""
    doc = MagicMock()
    doc.__enter__ = MagicMock(return_value=doc)
    doc.__exit__ = MagicMock(return_value=False)
    doc.__len__ = MagicMock(return_value=len(pages_text))

    def _get_page(idx: int) -> MagicMock:
        page = MagicMock()
        page.get_text = MagicMock(return_value=pages_text[idx])
        return page

    doc.__getitem__ = MagicMock(side_effect=_get_page)
    return doc


class TestIsScannedPDF:
    def test_empty_document_is_not_scanned(self) -> None:
        doc = _make_doc([])
        assert _is_scanned_pdf(doc, min_chars_per_page=100) is False

    def test_all_pages_full_of_text_is_not_scanned(self) -> None:
        doc = _make_doc(["text " * 500] * 50)
        assert _is_scanned_pdf(doc, min_chars_per_page=100) is False

    def test_all_pages_empty_is_scanned(self) -> None:
        doc = _make_doc([""] * 50)
        assert _is_scanned_pdf(doc, min_chars_per_page=100) is True

    def test_pages_with_only_whitespace_treated_as_empty(self) -> None:
        doc = _make_doc(["   \n\t  "] * 50)
        assert _is_scanned_pdf(doc, min_chars_per_page=100) is True

    def test_threshold_just_above_avg_flags_as_scanned(self) -> None:
        doc = _make_doc(["a" * 50] * 50)
        assert _is_scanned_pdf(doc, min_chars_per_page=100) is True

    def test_threshold_just_below_avg_passes(self) -> None:
        doc = _make_doc(["a" * 100] * 50)
        # Average exactly equals threshold; strict < means it passes (not scanned)
        assert _is_scanned_pdf(doc, min_chars_per_page=100) is False

    def test_single_page_short_text_is_scanned_at_default_threshold(self) -> None:
        """A 1-page PDF with very little text is flagged. Operators can lower the threshold."""
        doc = _make_doc(["short"])
        assert _is_scanned_pdf(doc, min_chars_per_page=100) is True

    def test_sample_size_is_ten_percent(self) -> None:
        """For a 100-page doc with sample_ratio=0.1 we should read exactly 10 pages."""
        doc = _make_doc(["text " * 500] * 100)
        _is_scanned_pdf(doc, min_chars_per_page=100, sample_ratio=0.1)
        assert doc.__getitem__.call_count == 10

    def test_sample_size_rounds_up_to_at_least_one(self) -> None:
        """For tiny docs, sample size must be at least 1 even though 10% rounds to 0."""
        doc = _make_doc(["text"] * 3)
        _is_scanned_pdf(doc, min_chars_per_page=100, sample_ratio=0.1)
        assert doc.__getitem__.call_count >= 1

    def test_sample_size_capped_at_page_count(self) -> None:
        """sample_ratio > 1 should not try to sample more pages than exist."""
        doc = _make_doc(["text " * 500] * 4)
        _is_scanned_pdf(doc, min_chars_per_page=100, sample_ratio=2.0)
        assert doc.__getitem__.call_count == 4

    def test_random_sampling_uses_random_module(self) -> None:
        """Verify the function uses random.sample (not a fixed stride)."""
        doc = _make_doc(["text " * 500] * 100)
        with patch("app.rag.extraction.random.sample", wraps=lambda r, k: list(r)[:k]) as mock_sample:
            _is_scanned_pdf(doc, min_chars_per_page=100, sample_ratio=0.1)
        mock_sample.assert_called_once()


class TestExtractPDFRejectsScanned:
    def test_raises_scanned_pdf_error_when_doc_has_no_text(self) -> None:
        scanned_doc = _make_doc([""] * 10)
        with (
            patch("app.rag.extraction.fitz.open", return_value=scanned_doc),
            patch("app.rag.extraction.fitz.TOOLS"),
            patch("app.rag.extraction.pymupdf4llm.to_markdown") as mock_to_md,
        ):
            with pytest.raises(ScannedPDFError):
                _extract_pdf(b"%PDF-fake", "scanned.pdf")
        # Detection happens before extraction, so to_markdown is never called
        mock_to_md.assert_not_called()

    def test_error_attaches_source_name_to_exception(self) -> None:
        scanned_doc = _make_doc([""] * 10)
        with (
            patch("app.rag.extraction.fitz.open", return_value=scanned_doc),
            patch("app.rag.extraction.fitz.TOOLS"),
            patch("app.rag.extraction.pymupdf4llm.to_markdown"),
        ):
            with pytest.raises(ScannedPDFError) as exc_info:
                _extract_pdf(b"%PDF-fake", "secret-report.pdf")
        assert exc_info.value.source_name == "secret-report.pdf"

    def test_user_facing_message_does_not_leak_source_name(self) -> None:
        """str(exc) must not include the filename — it is logged separately."""
        scanned_doc = _make_doc([""] * 10)
        with (
            patch("app.rag.extraction.fitz.open", return_value=scanned_doc),
            patch("app.rag.extraction.fitz.TOOLS"),
            patch("app.rag.extraction.pymupdf4llm.to_markdown"),
        ):
            with pytest.raises(ScannedPDFError) as exc_info:
                _extract_pdf(b"%PDF-fake", "/internal/path/secret-report.pdf")
        assert "secret-report.pdf" not in str(exc_info.value)
        assert "/internal/path/" not in str(exc_info.value)
        assert str(exc_info.value) == ScannedPDFError.USER_MESSAGE

    def test_text_pdf_not_rejected(self) -> None:
        """A born-digital PDF with text passes through to the batch loop."""
        text_doc = _make_doc(["lorem ipsum " * 50] * 10)
        with (
            patch("app.rag.extraction.fitz.open", return_value=text_doc),
            patch("app.rag.extraction.fitz.TOOLS"),
            patch("app.rag.extraction.pymupdf4llm.to_markdown", return_value="content") as mock_to_md,
        ):
            result = _extract_pdf(b"%PDF-fake", "real.pdf")
        mock_to_md.assert_called()  # extraction proceeded
        assert "content" in result.markdown

    def test_threshold_is_read_from_settings(self) -> None:
        """The threshold value comes from RAG_SCANNED_PDF_MIN_CHARS_PER_PAGE."""
        # 50 chars/page would normally be rejected at default 100, but pass at threshold 10
        borderline_doc = _make_doc(["a" * 50] * 10)
        with (
            patch("app.rag.extraction.get_settings") as mock_settings,
            patch("app.rag.extraction.fitz.open", return_value=borderline_doc),
            patch("app.rag.extraction.fitz.TOOLS"),
            patch("app.rag.extraction.pymupdf4llm.to_markdown", return_value="md"),
        ):
            mock_settings.return_value.RAG_ALLOWED_EXTENSIONS = ""
            mock_settings.return_value.RAG_PDF_EXTRACTION_BATCH_SIZE = 10
            mock_settings.return_value.RAG_SCANNED_PDF_MIN_CHARS_PER_PAGE = 10
            # Should NOT raise — 50 > 10
            _extract_pdf(b"%PDF-fake", "borderline.pdf")
