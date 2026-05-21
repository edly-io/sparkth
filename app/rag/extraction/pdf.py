"""PDF extractor using PyMuPDF, with scanned-PDF detection and page batching."""

from typing import Any, Optional

import fitz  # type: ignore[import-untyped]  # PyMuPDF
import pymupdf4llm  # type: ignore[import-untyped]

from app.core.config import get_settings
from app.core.logger import get_logger
from app.rag.exceptions import ScannedPDFError
from app.rag.extraction.base import BaseExtractor
from app.rag.types import DocType, ExtractionResult

logger = get_logger(__name__)


class PDFExtractor(BaseExtractor):
    """Extracts text from PDF files using PyMuPDF, with scanned-PDF detection."""

    def extract(self, data: bytes, source_name: str, *, batch_size: Optional[int] = None) -> ExtractionResult:
        settings = get_settings()
        effective_batch_size = batch_size if batch_size is not None else settings.RAG_PDF_EXTRACTION_BATCH_SIZE
        with fitz.open(stream=data, filetype="pdf") as doc:
            try:
                if self._is_scanned_pdf(doc, min_chars_per_page=settings.RAG_SCANNED_PDF_MIN_CHARS_PER_PAGE):
                    raise ScannedPDFError(source_name)
                page_count = len(doc)
                parts: list[str] = []
                for start in range(0, page_count, effective_batch_size):
                    pages = list(range(start, min(start + effective_batch_size, page_count)))
                    batch_md = pymupdf4llm.to_markdown(doc=doc, pages=pages, page_chunks=False)
                    parts.append(batch_md)
                    # Release MuPDF's C-level font/image store between batches so peak
                    # RSS stays bounded regardless of total page count.
                    fitz.TOOLS.store_shrink(100)
            finally:
                fitz.TOOLS.store_shrink(100)
        md = "\n\n".join(parts).replace("\n-----\n", "\n\n")
        return ExtractionResult(
            markdown=md,
            doc_type=DocType.PDF,
            source_name=source_name,
            page_count=page_count,
        )

    @staticmethod
    def _summarize_per_page(counts: list[int], head: int = 10, tail: int = 5) -> str:
        """Format a per-page char-count list for DEBUG logs without flooding them.

        For short lists (<= head + tail), returns the full list. For longer lists,
        returns the first `head` and last `tail` entries with an ellipsis between,
        so a reviewer can still see the shape (e.g. "starts dense, tails off") on
        a 500-page document without scrolling through 500 integers.
        """
        if len(counts) <= head + tail:
            return repr(counts)
        return f"{counts[:head]!r} ... {counts[-tail:]!r}"

    def _is_scanned_pdf(self, doc: Any, min_chars_per_page: int) -> bool:
        """Detect scanned/image-only PDFs by walking pages with an early-exit guarantee.

        The decision is deterministic: a PDF is treated as scanned iff its
        average plain-text chars-per-page is strictly below
        `min_chars_per_page`. To avoid reading every page on born-digital
        documents, we walk in order and exit as soon as the running total
        crosses the threshold required for the whole document — at that
        point the remaining pages cannot pull the average below it even if
        they contribute zero characters.

        Cost is bounded: born-digital PDFs exit after 1–3 pages; scanned
        PDFs walk every page, but fitz's `get_text` on an image-only page
        is microseconds (no rendering — it reports an empty text layer).
        """
        page_count = len(doc)
        if page_count == 0:
            return False

        required_total = min_chars_per_page * page_count
        per_page_counts: list[int] = []
        cumulative = 0
        for i in range(page_count):
            chars = len(doc[i].get_text("text").strip())
            per_page_counts.append(chars)
            cumulative += chars
            if cumulative >= required_total:
                logger.debug(
                    "Scanned-PDF check: passed early at page %d/%d (cumulative=%d, required=%d, per-page so far=%s)",
                    i + 1,
                    page_count,
                    cumulative,
                    required_total,
                    self._summarize_per_page(per_page_counts),
                )
                return False

        logger.debug(
            "Scanned-PDF check: rejected after %d pages, avg %.1f chars/page (threshold %d, per-page=%s)",
            page_count,
            cumulative / page_count,
            min_chars_per_page,
            self._summarize_per_page(per_page_counts),
        )
        return True
