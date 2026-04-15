"""Unit tests for Slack RAG dispatch."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core_plugins.slack.config import SlackBotConfig
from app.core_plugins.slack.rag import answer_question
from app.rag.store import SimilarityResult


def _make_chunk(content: str) -> MagicMock:
    chunk = MagicMock()
    chunk.content = content
    return chunk


def _make_result(content: str, similarity: float = 0.85) -> SimilarityResult:
    return SimilarityResult(chunk=_make_chunk(content), similarity=similarity)


def _make_provider(embedding: list[float] | None = None) -> MagicMock:
    """Return a mock provider with embed_query returning the given embedding."""
    provider = MagicMock()
    provider.embed_query = AsyncMock(return_value=embedding or [0.1] * 384)
    return provider


def _make_store(results: list[SimilarityResult]) -> MagicMock:
    """Return a mock store with similarity_search returning the given results."""
    store = MagicMock()
    store.similarity_search = AsyncMock(return_value=results)
    return store


@pytest.mark.asyncio
async def test_returns_rag_answer_when_chunks_found() -> None:
    config = SlackBotConfig()
    mock_session = AsyncMock()
    provider = _make_provider()
    store = _make_store([_make_result("Recursion is a function that calls itself.")])

    from unittest.mock import patch

    with patch("app.core_plugins.slack.rag._store", store):
        answer, rag_matched = await answer_question(
            mock_session, user_id=1, question="what is recursion?", config=config, provider=provider
        )

    assert rag_matched is True
    assert "Recursion is a function that calls itself." in answer


@pytest.mark.asyncio
async def test_returns_fallback_when_no_chunks_found() -> None:
    config = SlackBotConfig(fallback_message="No answer found.")
    mock_session = AsyncMock()
    provider = _make_provider()
    store = _make_store([])

    from unittest.mock import patch

    with patch("app.core_plugins.slack.rag._store", store):
        answer, rag_matched = await answer_question(
            mock_session, user_id=1, question="who are you?", config=config, provider=provider
        )

    assert rag_matched is False
    assert answer == "No answer found."


@pytest.mark.asyncio
async def test_joins_multiple_chunks_with_newlines() -> None:
    config = SlackBotConfig()
    mock_session = AsyncMock()
    provider = _make_provider()
    store = _make_store([_make_result("First chunk."), _make_result("Second chunk.")])

    from unittest.mock import patch

    with patch("app.core_plugins.slack.rag._store", store):
        answer, rag_matched = await answer_question(
            mock_session, user_id=1, question="explain loops", config=config, provider=provider
        )

    assert "First chunk." in answer
    assert "Second chunk." in answer
    assert rag_matched is True


@pytest.mark.asyncio
async def test_similarity_search_receives_correct_params() -> None:
    config = SlackBotConfig()
    mock_session = AsyncMock()
    embedding = [0.5] * 384
    provider = _make_provider(embedding)
    store = _make_store([])

    from unittest.mock import patch

    with patch("app.core_plugins.slack.rag._store", store):
        await answer_question(
            mock_session,
            user_id=42,
            question="test",
            config=config,
            provider=provider,
            similarity_threshold=0.85,
            limit=3,
        )

    store.similarity_search.assert_awaited_once_with(
        session=mock_session,
        user_id=42,
        query_embedding=embedding,
        limit=3,
        similarity_threshold=0.85,
    )
