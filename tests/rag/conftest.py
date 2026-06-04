"""Shared fixtures for RAG tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _default_pdf_settings() -> Generator[None, None, None]:
    """Seed the int-typed PDF extraction settings so tests that don't care
    about them don't trip over MagicMock defaults.

    Tests that specifically test these settings override them with their
    own inner patch() context managers.
    """
    with patch("app.rag.extraction.pdf.get_rag_settings") as mock:
        mock.return_value.RAG_SCANNED_PDF_MIN_CHARS_PER_PAGE = 100
        mock.return_value.RAG_PDF_EXTRACTION_BATCH_SIZE = 10
        yield
