"""Tests for process-level embedding provider singleton."""

from unittest.mock import MagicMock, patch

import pytest

from app.rag.provider import EmbeddingProviderRegistry, embedding_provider


def _reset() -> None:
    embedding_provider.reset()


def test_get_before_init_raises() -> None:
    """get() must raise RuntimeError if called before init()."""
    _reset()
    with pytest.raises(RuntimeError, match="not initialized"):
        embedding_provider.get()


def test_init_warms_model() -> None:
    """init() must call get_embeddings_model() so that model is loaded immediately."""
    _reset()
    mock_provider = MagicMock()
    with patch.object(EmbeddingProviderRegistry, "_build_provider", return_value=mock_provider):
        embedding_provider.init()

    mock_provider.get_embeddings_model.assert_called_once()


def test_get_returns_same_instance() -> None:
    """Multiple calls to get() return exact same object."""
    _reset()
    mock_provider = MagicMock()
    with patch.object(EmbeddingProviderRegistry, "_build_provider", return_value=mock_provider):
        embedding_provider.init()

    assert embedding_provider.get() is embedding_provider.get()


def test_init_reads_settings() -> None:
    """init() passes RAG_EMBEDDING_PROVIDER and RAG_EMBEDDING_MODEL from settings."""
    _reset()
    mock_provider = MagicMock()
    with (
        patch.object(EmbeddingProviderRegistry, "_build_provider", return_value=mock_provider) as mock_build,
        patch("app.rag.provider.get_settings") as mock_settings,
    ):
        mock_settings.return_value.RAG_EMBEDDING_PROVIDER = "huggingface"
        mock_settings.return_value.RAG_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
        embedding_provider.init()

    mock_build.assert_called_once_with("huggingface", "sentence-transformers/all-MiniLM-L6-v2")


def test_reset_clears_singleton() -> None:
    """reset() sets provider back to None."""
    _reset()
    mock_provider = MagicMock()
    with patch.object(EmbeddingProviderRegistry, "_build_provider", return_value=mock_provider):
        embedding_provider.init()

    assert embedding_provider.get() is mock_provider
    embedding_provider.reset()

    with pytest.raises(RuntimeError):
        embedding_provider.get()
