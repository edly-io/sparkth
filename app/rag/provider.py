"""Process-level embedding provider singleton.

Call init_provider() once during application startup (inside FastAPI lifespan).
All other code calls get_provider() to obtain warmed instance.
"""

from app.core.config import get_settings
from app.core.logger import get_logger
from app.rag.embeddings import (
    DEFAULT_EMBEDDING_DIMENSIONS,
    BaseEmbeddingProvider,
    get_embedding_provider,
)
from app.rag.memory_profiler import log_memory_snapshot

logger = get_logger(__name__)

_provider: BaseEmbeddingProvider | None = None


def _build_provider(provider_name: str, model_name: str) -> BaseEmbeddingProvider:
    """Construct provider instance. Separated so tests can patch it."""
    return get_embedding_provider(provider_name, model=model_name, dims=DEFAULT_EMBEDDING_DIMENSIONS)


def init_provider() -> BaseEmbeddingProvider:
    """Create provider and warm model.

    Must be called once during application startup before server begins
    serving requests. Calling it a second time is a no-op (returns existing
    instance).
    """
    global _provider
    if _provider is not None:
        return _provider

    settings = get_settings()
    provider_name = settings.RAG_EMBEDDING_PROVIDER
    model_name = settings.RAG_EMBEDDING_MODEL

    logger.info(
        "Initializing embedding provider: provider=%s model=%s",
        provider_name,
        model_name,
    )

    log_memory_snapshot(label="before_model_load")

    _provider = _build_provider(provider_name, model_name)
    _provider.get_embeddings_model()  # warm: loads weights into memory now

    log_memory_snapshot(label="after_model_load")

    logger.info("Embedding provider ready.")
    return _provider


def get_provider() -> BaseEmbeddingProvider:
    """Return process-level singleton provider.

    Raises RuntimeError if init_provider() has not been called.
    """
    if _provider is None:
        raise RuntimeError(
            "Embedding provider not initialized. init_provider() must be called during application startup."
        )
    return _provider


def reset_provider() -> None:
    """Reset singleton to None. For use in tests only."""
    global _provider
    _provider = None
