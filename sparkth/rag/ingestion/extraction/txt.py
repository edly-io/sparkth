"""Plain-text and Markdown extractor."""

from sparkth.rag.enums import DocType
from sparkth.rag.ingestion.extraction.base import BaseExtractor
from sparkth.rag.types import ExtractionResult


class TXTExtractor(BaseExtractor):
    """Extracts text from plain-text and Markdown files."""

    def extract(self, data: bytes, source_name: str) -> ExtractionResult:
        return ExtractionResult(
            markdown=data.decode("utf-8", errors="replace"),
            doc_type=DocType.TXT,
            source_name=source_name,
        )
