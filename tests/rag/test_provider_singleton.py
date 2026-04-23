"""Tests for process-level embedding provider singleton."""

from unittest.mock import MagicMock, patch

import pytest


def _reset() -> None:
    """Helper: reset singleton between tests."""
    from app.rag.provider import reset_provider

    reset_provider()


def test_get_provider_before_init_raises() -> None:
    """get_provider() must raise RuntimeError if called before init_provider()."""
    _reset()
    from app.rag.provider import get_provider

    with pytest.raises(RuntimeError, match="not initialized"):
        get_provider()


def test_init_provider_warms_model() -> None:
    """init_provider() must call get_embeddings_model() so that model is loaded immediately."""
    _reset()
    from app.rag.provider import init_provider

    mock_provider = MagicMock()
    with patch("app.rag.provider._build_provider", return_value=mock_provider):
        init_provider()

    mock_provider.get_embeddings_model.assert_called_once()


def test_get_provider_returns_same_instance() -> None:
    """Multiple calls to get_provider() return exact same object."""
    _reset()
    from app.rag.provider import get_provider, init_provider

    mock_provider = MagicMock()
    with patch("app.rag.provider._build_provider", return_value=mock_provider):
        init_provider()

    assert get_provider() is get_provider()


def test_init_provider_reads_settings() -> None:
    """init_provider() passes RAG_EMBEDDING_PROVIDER and RAG_EMBEDDING_MODEL from settings."""
    _reset()
    from app.rag.provider import init_provider

    mock_provider = MagicMock()
    with (
        patch("app.rag.provider._build_provider", return_value=mock_provider) as mock_build,
        patch("app.rag.provider.get_settings") as mock_settings,
    ):
        mock_settings.return_value.RAG_EMBEDDING_PROVIDER = "huggingface"
        mock_settings.return_value.RAG_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
        init_provider()

    mock_build.assert_called_once_with("huggingface", "sentence-transformers/all-MiniLM-L6-v2")


def test_reset_provider_clears_singleton() -> None:
    """reset_provider() sets singleton back to None (for use in tests)."""
    _reset()
    from app.rag.provider import get_provider, init_provider, reset_provider

    mock_provider = MagicMock()
    with patch("app.rag.provider._build_provider", return_value=mock_provider):
        init_provider()

    assert get_provider() is mock_provider
    reset_provider()

    with pytest.raises(RuntimeError):
        get_provider()
