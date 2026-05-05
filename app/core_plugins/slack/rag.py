"""RAG dispatch for the Slack TA Bot plugin."""

import httpx
from langchain_core.exceptions import LangChainException
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logger import get_logger
from app.core_plugins.slack.config import SlackConfig
from app.core_plugins.slack.synthesis import synthesize_answer
from app.llm.providers import BaseChatProvider
from app.rag.context_service import RAGContextService, format_chunks_as_context
from app.rag.embeddings import BaseEmbeddingProvider
from app.rag.provider import get_provider
from app.rag.store import SimilarityResult, VectorStoreService

logger = get_logger(__name__)

# Module-level singleton
_store: VectorStoreService = VectorStoreService()

logger = get_logger(__name__)

# Module-level singleton — embedding model and vector store loaded once per process
_rag_service: RAGContextService = RAGContextService()


_SIMILARITY_THRESHOLD = 0.5


async def answer_question(
    session: AsyncSession,
    user_id: int,
    question: str,
    config: SlackConfig,
    similarity_threshold: float = _SIMILARITY_THRESHOLD,
    limit: int = 5,
    provider: BaseEmbeddingProvider | None = None,
    llm_provider: BaseChatProvider | None = None,
) -> tuple[str, bool]:
    """Embed question, rank sections, search vector store, return (answer, rag_matched).

    Mirrors the chat RAG flow when allowed_sources are configured:
      1. Embed the query.
      2. Rank document sections by title similarity per source.
      3. Run similarity search filtered to the top-ranked sections.
      4. Merge and re-rank results across all sources.
      5. (Optional) Synthesize a natural-language answer via LLM.

    Falls back to a broad similarity search across all user content when
    no allowed_sources are configured.

    Returns (config.fallback_message, False) when no chunks meet the threshold.
    provider defaults to the RAGContextService embedding provider; pass a mock for testing.
    llm_provider, when set, sends the question + chunks to an LLM for synthesis.
    """
    embedding_provider = provider or get_provider()
    query_embedding = await embedding_provider.embed_query(question)

    all_results: list[SimilarityResult] = []
    source_names = config.allowed_sources

    if source_names:
        for source_name in source_names:
            ranked_sections = await _rag_service.rank_sections(
                session=session,
                user_id=user_id,
                source_name=source_name,
                query_embedding=query_embedding,
            )
            section_filter = list({s["section"] for s in ranked_sections if s["section"]}) or None

            results = await _rag_service.search_with_embedding(
                session=session,
                user_id=user_id,
                source_name=source_name,
                query_embedding=query_embedding,
                limit=limit,
                similarity_threshold=similarity_threshold,
                sections=section_filter,
            )
            all_results.extend(results)

        # Re-rank merged results and keep the top limit
        all_results.sort(key=lambda r: r.similarity, reverse=True)
        all_results = all_results[:limit]
    else:
        # No source filter: broad search across all user content
        all_results = await _rag_service._store.similarity_search(
            session=session,
            user_id=user_id,
            query_embedding=query_embedding,
            limit=limit,
            similarity_threshold=similarity_threshold,
        )

    logger.info(
        "RAG search for user_id=%d found %d chunks (threshold=%.2f, sources=%s)",
        user_id,
        len(all_results),
        similarity_threshold,
        source_names or "all",
    )

    if not all_results:
        return config.fallback_message, False

    # Group results by source and format
    sources_seen: list[str] = []
    results_by_source: dict[str, list[SimilarityResult]] = {}
    for r in all_results:
        sname = r.chunk.source_name
        if sname not in results_by_source:
            sources_seen.append(sname)
            results_by_source[sname] = []
        results_by_source[sname].append(r)

    formatted_context = "\n\n".join(format_chunks_as_context(sname, results_by_source[sname]) for sname in sources_seen)

    if llm_provider:
        try:
            answer = await synthesize_answer(
                question=question,
                context=formatted_context,
                provider=llm_provider,
            )
            return answer, True
        except (LangChainException, ValidationError, ValueError, RuntimeError, httpx.RemoteProtocolError) as exc:
            logger.warning(
                "LLM synthesis failed for user_id=%d, falling back to raw chunks: %s: %s",
                user_id,
                type(exc).__name__,
                exc,
            )

    return f"AI summary is not available at the moment, but here is what RAG found:\n\n{formatted_context}", True
