"""RAG dispatch for the Slack TA Bot plugin."""

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logger import get_logger
from app.core_plugins.slack.config import SlackBotConfig
from app.rag.embeddings import BaseEmbeddingProvider
from app.rag.provider import get_provider
from app.rag.store import VectorStoreService

logger = get_logger(__name__)

# Module-level singleton
_store: VectorStoreService = VectorStoreService()


async def answer_question(
    session: AsyncSession,
    user_id: int,
    question: str,
    config: SlackBotConfig,
    similarity_threshold: float = 0.3,
    limit: int = 5,
    provider: BaseEmbeddingProvider | None = None,
) -> tuple[str, bool]:
    """Embed question, search vector store, return (answer, rag_matched).

    Returns (config.fallback_message, False) when no chunks meet the threshold.
    provider defaults to HuggingFaceEmbeddingProvider; pass a mock for testing.
    """
    embedding_provider = provider or get_provider()
    query_embedding = await embedding_provider.embed_query(question)

    results = await _store.similarity_search(
        session=session,
        user_id=user_id,
        query_embedding=query_embedding,
        limit=limit,
        similarity_threshold=similarity_threshold,
        source_names=config.allowed_sources or None,
    )

    logger.info(
        "RAG search for user_id=%d found %d chunks (threshold=%.2f)",
        user_id,
        len(results),
        similarity_threshold,
    )

    if not results:
        return config.fallback_message, False

    answer = "\n\n".join(r.chunk.content for r in results)
    return answer, True
