"""Tests for the page-batched PDF extraction loop in _extract_pdf."""

from unittest.mock import MagicMock, patch

from app.rag.extraction import _extract_pdf


def _make_doc(page_count: int) -> MagicMock:
    """Mock doc with enough per-page text to pass the scanned-PDF check."""
    doc = MagicMock()
    doc.__enter__ = MagicMock(return_value=doc)
    doc.__exit__ = MagicMock(return_value=False)
    doc.__len__ = MagicMock(return_value=page_count)
    page = MagicMock()
    page.get_text = MagicMock(return_value="lorem ipsum " * 50)
    doc.__getitem__ = MagicMock(return_value=page)
    return doc


def _pages_kwargs(mock_to_markdown: MagicMock) -> list[list[int]]:
    """Extract the `pages` kwarg from every call to pymupdf4llm.to_markdown."""
    return [call.kwargs["pages"] for call in mock_to_markdown.call_args_list]


class TestBatchingLoop:
    def test_single_batch_when_pages_fit(self) -> None:
        """A 3-page doc with batch_size=10 makes one call covering pages [0, 1, 2]."""
        with (
            patch("app.rag.extraction.fitz.open", return_value=_make_doc(3)),
            patch("app.rag.extraction.fitz.TOOLS"),
            patch("app.rag.extraction.pymupdf4llm.to_markdown", return_value="md") as mock_to_md,
        ):
            _extract_pdf(b"%PDF-fake", "small.pdf", batch_size=10)

        assert _pages_kwargs(mock_to_md) == [[0, 1, 2]]

    def test_evenly_divisible_doc(self) -> None:
        """A 20-page doc with batch_size=10 produces exactly two equal batches."""
        with (
            patch("app.rag.extraction.fitz.open", return_value=_make_doc(20)),
            patch("app.rag.extraction.fitz.TOOLS"),
            patch("app.rag.extraction.pymupdf4llm.to_markdown", return_value="md") as mock_to_md,
        ):
            _extract_pdf(b"%PDF-fake", "doc.pdf", batch_size=10)

        pages_seen = _pages_kwargs(mock_to_md)
        assert pages_seen == [list(range(0, 10)), list(range(10, 20))]

    def test_last_partial_batch(self) -> None:
        """A 25-page doc with batch_size=10 makes 3 batches with the last one half-sized."""
        with (
            patch("app.rag.extraction.fitz.open", return_value=_make_doc(25)),
            patch("app.rag.extraction.fitz.TOOLS"),
            patch("app.rag.extraction.pymupdf4llm.to_markdown", return_value="md") as mock_to_md,
        ):
            _extract_pdf(b"%PDF-fake", "doc.pdf", batch_size=10)

        pages_seen = _pages_kwargs(mock_to_md)
        assert pages_seen == [list(range(0, 10)), list(range(10, 20)), list(range(20, 25))]

    def test_batch_size_kwarg_overrides_setting(self) -> None:
        """An explicit batch_size kwarg wins over RAG_PDF_EXTRACTION_BATCH_SIZE."""
        with (
            patch("app.rag.extraction.fitz.open", return_value=_make_doc(6)),
            patch("app.rag.extraction.fitz.TOOLS"),
            patch("app.rag.extraction.pymupdf4llm.to_markdown", return_value="md") as mock_to_md,
        ):
            _extract_pdf(b"%PDF-fake", "doc.pdf", batch_size=2)

        # 6 pages / batch_size=2 → 3 batches of 2
        assert _pages_kwargs(mock_to_md) == [[0, 1], [2, 3], [4, 5]]

    def test_batch_size_from_env_when_kwarg_omitted(self) -> None:
        """When batch_size is None, _extract_pdf reads RAG_PDF_EXTRACTION_BATCH_SIZE."""
        with (
            patch("app.rag.extraction.get_settings") as mock_settings,
            patch("app.rag.extraction.fitz.open", return_value=_make_doc(6)),
            patch("app.rag.extraction.fitz.TOOLS"),
            patch("app.rag.extraction.pymupdf4llm.to_markdown", return_value="md") as mock_to_md,
        ):
            mock_settings.return_value.RAG_ALLOWED_EXTENSIONS = ""
            mock_settings.return_value.RAG_SCANNED_PDF_MIN_CHARS_PER_PAGE = 0  # never scanned
            mock_settings.return_value.RAG_PDF_EXTRACTION_BATCH_SIZE = 3
            _extract_pdf(b"%PDF-fake", "doc.pdf")  # no batch_size kwarg

        assert _pages_kwargs(mock_to_md) == [[0, 1, 2], [3, 4, 5]]

    def test_batches_concatenated_in_order(self) -> None:
        """Markdown from each batch is joined into the final result in batch order."""
        with (
            patch("app.rag.extraction.fitz.open", return_value=_make_doc(6)),
            patch("app.rag.extraction.fitz.TOOLS"),
            patch(
                "app.rag.extraction.pymupdf4llm.to_markdown",
                side_effect=["FIRST", "SECOND", "THIRD"],
            ),
        ):
            result = _extract_pdf(b"%PDF-fake", "doc.pdf", batch_size=2)

        idx_first = result.markdown.index("FIRST")
        idx_second = result.markdown.index("SECOND")
        idx_third = result.markdown.index("THIRD")
        assert idx_first < idx_second < idx_third

    def test_page_count_reflects_total_pages_not_batches(self) -> None:
        with (
            patch("app.rag.extraction.fitz.open", return_value=_make_doc(25)),
            patch("app.rag.extraction.fitz.TOOLS"),
            patch("app.rag.extraction.pymupdf4llm.to_markdown", return_value="md"),
        ):
            result = _extract_pdf(b"%PDF-fake", "doc.pdf", batch_size=10)

        assert result.page_count == 25
