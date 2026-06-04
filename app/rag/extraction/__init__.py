"""
Converts PDF / DOCX / Google Doc HTML export into structured Markdown,
preserving heading hierarchy, lists, and tables for downstream chunking.

"""

from pathlib import Path

from app.lib.log import get_logger
from app.rag.exceptions import UnsupportedFileTypeError
from app.rag.extraction.base import BaseExtractor
from app.rag.extraction.docx import DocxExtractor
from app.rag.extraction.html import HTMLExtractor
from app.rag.extraction.pdf import PDFExtractor
from app.rag.extraction.txt import TXTExtractor
from app.rag.types import ExtractionResult

logger = get_logger(__name__)

_html = HTMLExtractor()
_txt = TXTExtractor()

_REGISTRY: dict[str, BaseExtractor] = {
    "pdf": PDFExtractor(),
    "docx": DocxExtractor(),
    "html": _html,
    "htm": _html,
    "txt": _txt,
    "md": _txt,
}

SUPPORTED_EXTENSIONS_FOR_EXTRACTION: frozenset[str] = frozenset(_REGISTRY)


def check_extraction_eligibility(filename: str) -> None:
    """Raise UnsupportedFileTypeError if *filename*'s type cannot be extracted.

    This is the single source of truth for which files RAG can ingest. Clients
    can call it to check eligibility (e.g. before downloading) without invoking
    the full extraction pipeline.
    """
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix not in SUPPORTED_EXTENSIONS_FOR_EXTRACTION:
        raise UnsupportedFileTypeError(f"Unsupported file type '.{suffix}' for RAG ingestion.")


def extract_to_markdown(data: bytes, filename: str) -> ExtractionResult:
    """
    Main entry point. Accepts raw file bytes and the original filename,
    returns an ExtractionResult with structured Markdown ready for chunking.

    Usage:
        result = extract_to_markdown(file_bytes, "lecture_notes.pdf")
    """
    suffix = Path(filename).suffix.lower().lstrip(".")
    extractor = _REGISTRY.get(suffix)

    if extractor is None:
        raise ValueError(
            f"Unsupported file type '.{suffix}' for extraction. file: '{filename}'. Supported: {list(_REGISTRY.keys())}"
        )

    logger.info("Extracting '%s' as %s", filename, suffix.upper())
    result = extractor.extract(data, filename)

    for w in result.warnings:
        logger.warning(w)

    logger.info(
        "Extraction complete: %s → %d chars of Markdown",
        filename,
        len(result.markdown),
    )
    return result


__all__ = [
    "SUPPORTED_EXTENSIONS_FOR_EXTRACTION",
    "BaseExtractor",
    "DocxExtractor",
    "ExtractionResult",
    "HTMLExtractor",
    "PDFExtractor",
    "TXTExtractor",
    "check_extraction_eligibility",
    "extract_to_markdown",
]
