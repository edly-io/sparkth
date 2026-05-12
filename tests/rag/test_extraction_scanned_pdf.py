"""Tests for scanned/image-only PDF detection in _extract_pdf.

We assert behaviour at two levels:
  * `_is_scanned_pdf` — the page-sampling primitive.
  * `_extract_pdf`    — the integration point that raises ScannedPDFError.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.rag.exceptions import ScannedPDFError
from app.rag.extraction import _extract_pdf, _is_scanned_pdf, _summarize_per_page


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

    def test_decision_is_deterministic(self) -> None:
        """Repeated calls on the same doc return the same answer and read the same pages."""
        pages_text = ["lorem ipsum " * 50] * 20
        results = []
        call_counts = []
        for _ in range(5):
            doc = _make_doc(pages_text)
            results.append(_is_scanned_pdf(doc, min_chars_per_page=100))
            call_counts.append(doc.__getitem__.call_count)
        assert len(set(results)) == 1  # same answer every time
        assert len(set(call_counts)) == 1  # same pages read every time

    def test_born_digital_doc_exits_early(self) -> None:
        """A doc whose first page already crosses the threshold should not read every page."""
        page_count = 50
        # Page 0 has way more than 50 * 100 chars; later pages should never be touched.
        pages_text = ["x" * (100 * page_count + 1)] + ["x" * 100] * (page_count - 1)
        doc = _make_doc(pages_text)
        result = _is_scanned_pdf(doc, min_chars_per_page=100)
        assert result is False
        assert doc.__getitem__.call_count == 1

    def test_scanned_doc_walks_every_page(self) -> None:
        """An image-only doc has to look at every page to be sure (no early-exit applies)."""
        page_count = 20
        doc = _make_doc([""] * page_count)
        result = _is_scanned_pdf(doc, min_chars_per_page=100)
        assert result is True
        assert doc.__getitem__.call_count == page_count

    def test_mixed_content_near_threshold_is_deterministic(self) -> None:
        """A small doc with one rich page and one sparse page: same answer every run."""
        # 2-page doc, threshold 100. Page 0: 150 chars, page 1: 50 chars.
        # Total = 200; required = 100 * 2 = 200. Cumulative reaches required on page 1,
        # not page 0, so order matters but the answer is fixed.
        pages_text = ["x" * 150, "y" * 50]
        results = [_is_scanned_pdf(_make_doc(pages_text), min_chars_per_page=100) for _ in range(10)]
        assert all(r == results[0] for r in results)

    def test_walks_pages_in_order(self) -> None:
        """First page read is index 0, second is index 1, etc. (no random ordering)."""
        doc = _make_doc([""] * 5)
        _is_scanned_pdf(doc, min_chars_per_page=100)
        indices_read = [call.args[0] for call in doc.__getitem__.call_args_list]
        assert indices_read == [0, 1, 2, 3, 4]


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


class TestSummarizePerPage:
    def test_short_list_returned_in_full(self) -> None:
        counts = [10, 20, 30]
        assert _summarize_per_page(counts) == repr(counts)

    def test_list_at_boundary_returned_in_full(self) -> None:
        """A list whose length equals head + tail must still be shown in full."""
        counts = list(range(15))  # default head=10 + tail=5
        assert _summarize_per_page(counts) == repr(counts)

    def test_long_list_truncated_with_ellipsis(self) -> None:
        counts = list(range(500))
        summary = _summarize_per_page(counts)
        assert summary.startswith(repr(counts[:10]))
        assert summary.endswith(repr(counts[-5:]))
        assert "..." in summary

    def test_truncated_summary_is_bounded_in_size(self) -> None:
        """A 5000-page summary should still be much smaller than the full list repr."""
        counts = list(range(5000))
        summary = _summarize_per_page(counts)
        assert len(summary) < len(repr(counts)) // 10  # at least 10x smaller

    def test_custom_head_and_tail(self) -> None:
        counts = list(range(100))
        summary = _summarize_per_page(counts, head=3, tail=2)
        assert summary.startswith(repr([0, 1, 2]))
        assert summary.endswith(repr([98, 99]))
