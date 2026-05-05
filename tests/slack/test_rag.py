"""Unit tests for Slack RAG dispatch."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import LangChainException

from app.core_plugins.slack.config import SlackConfig
from app.core_plugins.slack.rag import answer_question
from app.rag.store import SimilarityResult


def _make_chunk(content: str) -> MagicMock:
    chunk = MagicMock()
    chunk.content = content
    chunk.chapter = None
    chunk.section = None
    chunk.subsection = None
    return chunk


def _make_result(content: str, similarity: float = 0.85) -> SimilarityResult:
    return SimilarityResult(chunk=_make_chunk(content), similarity=similarity)


def _make_provider(embedding: list[float] | None = None) -> MagicMock:
    """Return a mock provider with embed_query returning the given embedding."""
    provider = MagicMock()
    provider.embed_query = AsyncMock(return_value=embedding or [0.1] * 384)
    return provider


@pytest.mark.asyncio
async def test_returns_rag_answer_when_chunks_found() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    provider = _make_provider()
    result = _make_result("Recursion is a function that calls itself.")
    result.chunk.source_name = "docs.pdf"

    with patch("app.core_plugins.slack.rag._rag_service") as mock_svc:
        mock_svc._embedding_provider = provider
        mock_svc._store = MagicMock()
        mock_svc._store.similarity_search = AsyncMock(return_value=[result])
        answer, rag_matched = await answer_question(
            mock_session, user_id=1, question="what is recursion?", config=config, provider=provider
        )

    assert rag_matched is True
    assert "Recursion is a function that calls itself." in answer


@pytest.mark.asyncio
async def test_returns_fallback_when_no_chunks_found() -> None:
    config = SlackConfig(fallback_message="No answer found.")
    mock_session = AsyncMock()
    provider = _make_provider()

    with patch("app.core_plugins.slack.rag._rag_service") as mock_svc:
        mock_svc._embedding_provider = provider
        mock_svc._store = MagicMock()
        mock_svc._store.similarity_search = AsyncMock(return_value=[])
        answer, rag_matched = await answer_question(
            mock_session, user_id=1, question="who are you?", config=config, provider=provider
        )

    assert rag_matched is False
    assert answer == "No answer found."


@pytest.mark.asyncio
async def test_joins_multiple_chunks_with_newlines() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    provider = _make_provider()
    r1 = _make_result("First chunk.")
    r1.chunk.source_name = "docs.pdf"
    r2 = _make_result("Second chunk.")
    r2.chunk.source_name = "docs.pdf"

    with patch("app.core_plugins.slack.rag._rag_service") as mock_svc:
        mock_svc._embedding_provider = provider
        mock_svc._store = MagicMock()
        mock_svc._store.similarity_search = AsyncMock(return_value=[r1, r2])
        answer, rag_matched = await answer_question(
            mock_session, user_id=1, question="explain loops", config=config, provider=provider
        )

    assert "First chunk." in answer
    assert "Second chunk." in answer
    assert rag_matched is True


@pytest.mark.asyncio
async def test_allowed_sources_passed_to_similarity_search() -> None:
    config = SlackConfig(allowed_sources=["python.pdf", "ai.pdf"])
    mock_session = AsyncMock()
    provider = _make_provider()

    with patch("app.core_plugins.slack.rag._rag_service") as mock_svc:
        mock_svc._embedding_provider = provider
        mock_svc.rank_sections = AsyncMock(return_value=[])
        mock_svc.search_with_embedding = AsyncMock(return_value=[])
        await answer_question(mock_session, user_id=1, question="test", config=config, provider=provider)

    assert mock_svc.search_with_embedding.await_count == 2
    calls = mock_svc.search_with_embedding.call_args_list
    source_names_used = [c.kwargs["source_name"] for c in calls]
    assert source_names_used == ["python.pdf", "ai.pdf"]


@pytest.mark.asyncio
async def test_empty_allowed_sources_passes_none_to_similarity_search() -> None:
    config = SlackConfig(allowed_sources=[])
    mock_session = AsyncMock()
    provider = _make_provider()

    with patch("app.core_plugins.slack.rag._rag_service") as mock_svc:
        mock_svc._embedding_provider = provider
        mock_svc._store = MagicMock()
        mock_svc._store.similarity_search = AsyncMock(return_value=[])
        await answer_question(mock_session, user_id=1, question="test", config=config, provider=provider)

    mock_svc._store.similarity_search.assert_awaited_once()
    _, kwargs = mock_svc._store.similarity_search.call_args
    assert "source_names" not in kwargs or kwargs.get("source_names") is None


@pytest.mark.asyncio
async def test_similarity_search_receives_correct_params() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    embedding = [0.5] * 384
    provider = _make_provider(embedding)

    with patch("app.core_plugins.slack.rag._rag_service") as mock_svc:
        mock_svc._embedding_provider = provider
        mock_svc._store = MagicMock()
        mock_svc._store.similarity_search = AsyncMock(return_value=[])
        await answer_question(
            mock_session,
            user_id=42,
            question="test",
            config=config,
            provider=provider,
            similarity_threshold=0.85,
            limit=3,
        )

    mock_svc._store.similarity_search.assert_awaited_once_with(
        session=mock_session,
        user_id=42,
        query_embedding=embedding,
        limit=3,
        similarity_threshold=0.85,
    )


@pytest.mark.asyncio
async def test_returns_synthesized_answer_when_llm_provider_given() -> None:
    """When llm_provider is passed and chunks exist, synthesize_answer is called and its result returned."""
    config = SlackConfig()
    mock_session = AsyncMock()
    provider = _make_provider()

    chunk = _make_chunk("Recursion calls itself.")
    chunk.source_name = "python.pdf"
    results = [SimilarityResult(chunk=chunk, similarity=0.9)]

    llm_provider = MagicMock()

    with (
        patch("app.core_plugins.slack.rag._rag_service") as mock_svc,
        patch("app.core_plugins.slack.rag.synthesize_answer", new_callable=AsyncMock) as mock_synthesize,
    ):
        mock_svc._embedding_provider = provider
        mock_svc._store = MagicMock()
        mock_svc._store.similarity_search = AsyncMock(return_value=results)
        mock_synthesize.return_value = "Synthesized: recursion is self-referential."

        answer, rag_matched = await answer_question(
            mock_session,
            user_id=1,
            question="what is recursion?",
            config=config,
            provider=provider,
            llm_provider=llm_provider,
        )

    assert rag_matched is True
    assert answer == "Synthesized: recursion is self-referential."
    mock_synthesize.assert_awaited_once_with(
        question="what is recursion?",
        context=mock_synthesize.call_args.kwargs["context"],
        provider=llm_provider,
    )


@pytest.mark.asyncio
async def test_returns_raw_chunks_when_no_llm_provider() -> None:
    """When llm_provider is None, returns prefixed message with raw formatted chunks."""
    config = SlackConfig()
    mock_session = AsyncMock()
    provider = _make_provider()

    chunk = _make_chunk("Recursion calls itself.")
    chunk.source_name = "python.pdf"
    results = [SimilarityResult(chunk=chunk, similarity=0.9)]

    with patch("app.core_plugins.slack.rag._rag_service") as mock_svc:
        mock_svc._embedding_provider = provider
        mock_svc._store = MagicMock()
        mock_svc._store.similarity_search = AsyncMock(return_value=results)
        answer, rag_matched = await answer_question(
            mock_session,
            user_id=1,
            question="what is recursion?",
            config=config,
            provider=provider,
        )

    assert rag_matched is True
    assert "Recursion calls itself." in answer


@pytest.mark.asyncio
async def test_synthesis_not_called_when_no_chunks() -> None:
    """When no chunks found, synthesis is skipped and fallback returned."""
    config = SlackConfig(fallback_message="No answer found.")
    mock_session = AsyncMock()
    provider = _make_provider()

    llm_provider = AsyncMock()

    with patch("app.core_plugins.slack.rag._rag_service") as mock_svc:
        mock_svc._embedding_provider = provider
        mock_svc._store = MagicMock()
        mock_svc._store.similarity_search = AsyncMock(return_value=[])
        answer, rag_matched = await answer_question(
            mock_session,
            user_id=1,
            question="what is recursion?",
            config=config,
            provider=provider,
            llm_provider=llm_provider,
        )

    assert rag_matched is False
    assert answer == "No answer found."
    llm_provider.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_falls_back_to_raw_chunks_on_synthesis_error() -> None:
    """When LLM synthesis raises, fall back to prefixed message with raw formatted chunks."""
    config = SlackConfig()
    mock_session = AsyncMock()
    provider = _make_provider()

    chunk = _make_chunk("Loops repeat code.")
    chunk.source_name = "python.pdf"
    results = [SimilarityResult(chunk=chunk, similarity=0.9)]

    llm_provider = AsyncMock()
    llm_provider.send_message = AsyncMock(side_effect=LangChainException("API rate limit"))

    with patch("app.core_plugins.slack.rag._rag_service") as mock_svc:
        mock_svc._embedding_provider = provider
        mock_svc._store = MagicMock()
        mock_svc._store.similarity_search = AsyncMock(return_value=results)
        answer, rag_matched = await answer_question(
            mock_session,
            user_id=1,
            question="what are loops?",
            config=config,
            provider=provider,
            llm_provider=llm_provider,
        )

    assert rag_matched is True
    assert "Loops repeat code." in answer
    llm_provider.send_message.assert_awaited_once()
