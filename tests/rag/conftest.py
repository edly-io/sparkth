"""Shared fixtures for RAG tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _allow_all_extensions() -> Generator[None, None, None]:
    """Patch RAG extraction settings so no extension is blocked by default.

    Also seeds the int-typed RAG_* settings used by _extract_pdf so tests
    that don't care about them don't trip over MagicMock defaults.

    Tests that specifically test these settings override them with their
    own inner patch() context managers.
    """
    with patch("app.rag.extraction.get_rag_settings") as mock:
        mock.return_value.RAG_ALLOWED_EXTENSIONS = ""
        mock.return_value.RAG_SCANNED_PDF_MIN_CHARS_PER_PAGE = 100
        mock.return_value.RAG_PDF_EXTRACTION_BATCH_SIZE = 10
        yield
