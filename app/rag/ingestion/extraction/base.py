"""Abstract base extractor."""

from abc import ABC, abstractmethod

from app.rag.types import ExtractionResult


class BaseExtractor(ABC):
    """Abstract base for file-type-specific extractors."""

    @abstractmethod
    def extract(self, data: bytes, source_name: str) -> ExtractionResult:
        """Extract content from raw bytes and return an ExtractionResult with structured Markdown."""
