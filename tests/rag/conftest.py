"""Shared fixtures for RAG tests.

The generic test environment is set by the sparkth.testing plugin (registered in the
root conftest), which also imports sparkth.main -> sparkth.core.models at startup. That
early import keeps the model registry stable for RAG tests.
"""

from collections.abc import Generator
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _default_pdf_settings() -> Generator[None, None, None]:
    """Seed the int-typed PDF extraction settings for tests that do not care about them."""
    with patch("sparkth.rag.ingestion.extraction.pdf.get_rag_settings") as mock:
        mock.return_value.RAG_SCANNED_PDF_MIN_CHARS_PER_PAGE = 100
        mock.return_value.RAG_PDF_EXTRACTION_BATCH_SIZE = 10
        yield
