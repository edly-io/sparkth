"""
Converts PDF / DOCX / Google Doc HTML export into structured Markdown,
preserving heading hierarchy, lists, and tables for downstream chunking.

"""

from pathlib import Path

from app.core.config import get_settings, parse_rag_allowed_extensions
from app.core.logger import get_logger
from app.rag.extraction.base import BaseExtractor
from app.rag.extraction.docx import DocxExtractor
from app.rag.extraction.html import HTMLExtractor
from app.rag.extraction.pdf import PDFExtractor
from app.rag.extraction.txt import TXTExtractor
from app.rag.types import ExtractionResult

logger = get_logger(__name__)

_REGISTRY: dict[str, BaseExtractor] = {
    "pdf": PDFExtractor(),
    "docx": DocxExtractor(),
    "html": HTMLExtractor(),
    "htm": HTMLExtractor(),
    "txt": TXTExtractor(),
    "md": TXTExtractor(),
}

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(_REGISTRY)


def extract_to_markdown(data: bytes, filename: str) -> ExtractionResult:
    """
    Main entry point. Accepts raw file bytes and the original filename,
    returns an ExtractionResult with structured Markdown ready for chunking.

    Usage:
        result = extract_to_markdown(file_bytes, "lecture_notes.pdf")
        print(result.markdown)
    """
    suffix = Path(filename).suffix.lower().lstrip(".")

    # This is defense-in-depth for non-Drive callers of extract_to_markdown
    allowed = parse_rag_allowed_extensions(get_settings().RAG_ALLOWED_EXTENSIONS)
    if allowed and suffix not in allowed:
        accepted = ", ".join(f".{e}" for e in allowed)
        raise ValueError(f"Unsupported file extension. Allowed: {accepted}.")

    extractor = _REGISTRY.get(suffix)

    if extractor is None:
        raise ValueError(f"Unsupported file type '.{suffix}' for '{filename}'. Supported: {list(_REGISTRY.keys())}")

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
    "BaseExtractor",
    "DocxExtractor",
    "ExtractionResult",
    "HTMLExtractor",
    "PDFExtractor",
    "SUPPORTED_EXTENSIONS",
    "TXTExtractor",
    "_REGISTRY",
    "extract_to_markdown",
]
