"""Tests for the embedding provider abstraction."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.rag.embeddings import (
    DEFAULT_EMBEDDING_DIMENSIONS,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_PROVIDER,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_PROVIDER_REGISTRY,
    HuggingFaceEmbeddingProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
)


class TestHuggingFaceEmbeddingProvider:
    def test_default_model_and_dimensions(self) -> None:
        provider = HuggingFaceEmbeddingProvider()
        assert provider.model_name == "sentence-transformers/all-MiniLM-L6-v2"
        assert provider.dimensions == 384
        assert provider.provider_name == "huggingface"

    def test_custom_model(self) -> None:
        provider = HuggingFaceEmbeddingProvider(model="custom/model", dims=768)
        assert provider.model_name == "custom/model"
        assert provider.dimensions == 768

    @patch("app.rag.embeddings.HuggingFaceEmbeddingProvider.get_embeddings_model")
    async def test_embed_documents(self, mock_get_model: MagicMock) -> None:
        mock_model = AsyncMock()
        mock_model.aembed_documents = AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])
        mock_get_model.return_value = mock_model

        provider = HuggingFaceEmbeddingProvider()
        result = await provider.embed_documents(["hello", "world"])

        mock_model.aembed_documents.assert_awaited_once_with(["hello", "world"])
        assert result == [[0.1, 0.2], [0.3, 0.4]]

    @patch("app.rag.embeddings.HuggingFaceEmbeddingProvider.get_embeddings_model")
    async def test_embed_query(self, mock_get_model: MagicMock) -> None:
        mock_model = AsyncMock()
        mock_model.aembed_query = AsyncMock(return_value=[0.5, 0.6])
        mock_get_model.return_value = mock_model

        provider = HuggingFaceEmbeddingProvider()
        result = await provider.embed_query("test query")

        mock_model.aembed_query.assert_awaited_once_with("test query")
        assert result == [0.5, 0.6]

    @patch("app.rag.embeddings.HuggingFaceEmbeddingProvider.get_embeddings_model")
    async def test_embed_documents_batching(self, mock_get_model: MagicMock) -> None:
        """Verify that large inputs are split into batches."""
        texts = [f"text_{i}" for i in range(EMBEDDING_BATCH_SIZE + 10)]

        mock_model = AsyncMock()
        # First call returns EMBEDDING_BATCH_SIZE embeddings, second returns 10
        mock_model.aembed_documents = AsyncMock(
            side_effect=[
                [[0.1]] * EMBEDDING_BATCH_SIZE,
                [[0.2]] * 10,
            ]
        )
        mock_get_model.return_value = mock_model

        provider = HuggingFaceEmbeddingProvider()
        result = await provider.embed_documents(texts)

        assert mock_model.aembed_documents.await_count == 2
        assert len(result) == EMBEDDING_BATCH_SIZE + 10


class TestOpenAIEmbeddingProvider:
    def test_default_model_and_dimensions(self) -> None:
        provider = OpenAIEmbeddingProvider(api_key="sk-test")
        assert provider.model_name == "text-embedding-3-small"
        assert provider.dimensions == 1536
        assert provider.provider_name == "openai"

    def test_custom_params(self) -> None:
        provider = OpenAIEmbeddingProvider(api_key="sk-test", model="text-embedding-3-large", dims=3072)
        assert provider.model_name == "text-embedding-3-large"
        assert provider.dimensions == 3072


class TestProviderRegistry:
    def test_registry_has_expected_providers(self) -> None:
        assert "huggingface" in EMBEDDING_PROVIDER_REGISTRY
        assert "openai" in EMBEDDING_PROVIDER_REGISTRY

    def test_default_provider_is_huggingface(self) -> None:
        assert DEFAULT_EMBEDDING_PROVIDER == "huggingface"
        assert DEFAULT_EMBEDDING_MODEL == "sentence-transformers/all-MiniLM-L6-v2"
        assert DEFAULT_EMBEDDING_DIMENSIONS == 384

    def test_get_embedding_provider_default(self) -> None:
        provider = get_embedding_provider()
        assert isinstance(provider, HuggingFaceEmbeddingProvider)

    def test_get_embedding_provider_openai(self) -> None:
        provider = get_embedding_provider("openai", api_key="sk-test")
        assert isinstance(provider, OpenAIEmbeddingProvider)

    def test_get_embedding_provider_invalid(self) -> None:
        with pytest.raises(ValueError, match="Unsupported embedding provider"):
            get_embedding_provider("invalid_provider")

    def test_get_embedding_provider_case_insensitive(self) -> None:
        provider = get_embedding_provider("HuggingFace")
        assert isinstance(provider, HuggingFaceEmbeddingProvider)
