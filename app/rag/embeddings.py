"""
Embedding provider abstraction following the same registry pattern
as ``app.core_plugins.chat.providers``.

Default provider uses HuggingFace ``all-MiniLM-L6-v2`` (384 dims, free, local).
OpenAI is available as an optional provider for users with API keys.
"""

from abc import ABC, abstractmethod

from langchain_core.embeddings import Embeddings as LCEmbeddings

from app.core.logger import get_logger

logger = get_logger(__name__)

EMBEDDING_BATCH_SIZE = 512


class BaseEmbeddingProvider(ABC):
    """Abstract base for embedding providers."""

    @abstractmethod
    def get_embeddings_model(self) -> LCEmbeddings:
        """Return a LangChain Embeddings instance."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the dimensionality of the embedding vectors."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider identifier (e.g. 'huggingface', 'openai')."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts in batches."""
        model = self.get_embeddings_model()
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = texts[i : i + EMBEDDING_BATCH_SIZE]
            embeddings = await model.aembed_documents(batch)
            all_embeddings.extend(embeddings)
        return all_embeddings

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query text."""
        model = self.get_embeddings_model()
        return await model.aembed_query(text)


class HuggingFaceEmbeddingProvider(BaseEmbeddingProvider):
    """Local embeddings via sentence-transformers (free, no API key required)."""

    def __init__(
        self,
        model: str = "sentence-transformers/all-MiniLM-L6-v2",
        dims: int = 384,
    ) -> None:
        self._model = model
        self._dimensions = dims

    def get_embeddings_model(self) -> LCEmbeddings:
        from langchain_huggingface import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(model_name=self._model)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def provider_name(self) -> str:
        return "huggingface"

    @property
    def model_name(self) -> str:
        return self._model


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """Cloud embeddings via OpenAI API (requires API key)."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dims: int = 1536,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._dimensions = dims

    def get_embeddings_model(self) -> LCEmbeddings:
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(  # type: ignore[call-arg]
            api_key=self._api_key,
            model=self._model,
            dimensions=self._dimensions,
        )

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model


EMBEDDING_PROVIDER_REGISTRY: dict[str, type[BaseEmbeddingProvider]] = {
    "huggingface": HuggingFaceEmbeddingProvider,
    "openai": OpenAIEmbeddingProvider,
}

DEFAULT_EMBEDDING_PROVIDER = "huggingface"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_EMBEDDING_DIMENSIONS = 384


def get_embedding_provider(
    provider_name: str = DEFAULT_EMBEDDING_PROVIDER,
    **kwargs: str | int,
) -> BaseEmbeddingProvider:
    """Instantiate an embedding provider by name."""
    provider_class = EMBEDDING_PROVIDER_REGISTRY.get(provider_name.lower())
    if not provider_class:
        supported = ", ".join(EMBEDDING_PROVIDER_REGISTRY.keys())
        raise ValueError(f"Unsupported embedding provider: {provider_name}. Supported: {supported}")
    return provider_class(**kwargs)
