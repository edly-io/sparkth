"""Unit tests for Slack RAG dispatch."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import LangChainException

from app.core_plugins.slack.config import SlackConfig
from app.core_plugins.slack.constants import (
    DRIVE_FILE_NOT_FOUND_MESSAGE,
    NO_FILES_RESOLVED_MESSAGE,
    RAG_NOT_READY_MESSAGE,
    RETRIEVAL_ERROR_MESSAGE,
    SLACK_MAX_AGENT_FILES,
)
from app.core_plugins.slack.models import ResponseType
from app.core_plugins.slack.rag import (
    _resolve_files_for_sources,
    answer_question,
)
from app.lib.rag import (
    DriveFileNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    RetrievedChunk,
)


@pytest.mark.asyncio
async def test_resolve_files_for_sources_filters_by_allowed_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Returns only DriveFile IDs whose source_name is in allowed_sources."""
    mock_session = AsyncMock()
    # Note: MagicMock's `name` kwarg is reserved (sets the mock's repr name, not the .name attribute).
    # We assign .name explicitly after construction so resolve_source_name() reads the intended value.
    f1 = MagicMock(id=10, mime_type="application/pdf")
    f1.name = "python.pdf"
    f2 = MagicMock(id=11, mime_type="application/pdf")
    f2.name = "ai.pdf"
    f3 = MagicMock(id=12, mime_type="application/pdf")
    f3.name = "biology.pdf"
    mock_files = [f1, f2, f3]
    exec_result = MagicMock()
    exec_result.all.return_value = mock_files
    mock_session.exec = AsyncMock(return_value=exec_result)

    result = await _resolve_files_for_sources(session=mock_session, user_id=1, allowed_sources=["python.pdf", "ai.pdf"])
    assert sorted(result) == [10, 11]


@pytest.mark.asyncio
async def test_resolve_files_for_sources_empty_returns_capped_owner_files() -> None:
    """When allowed_sources is empty, returns up to SLACK_MAX_AGENT_FILES owner files ordered by id ASC."""
    mock_session = AsyncMock()
    mock_files = [MagicMock(id=i, name=f"doc-{i}.pdf", mime_type="application/pdf") for i in range(1, 9)]
    exec_result = MagicMock()
    exec_result.all.return_value = mock_files
    mock_session.exec = AsyncMock(return_value=exec_result)

    result = await _resolve_files_for_sources(session=mock_session, user_id=1, allowed_sources=[])
    assert result == [1, 2, 3, 4, 5]
    assert len(result) == SLACK_MAX_AGENT_FILES


@pytest.mark.asyncio
async def test_resolve_files_for_sources_returns_empty_when_no_files() -> None:
    mock_session = AsyncMock()
    exec_result = MagicMock()
    exec_result.all.return_value = []
    mock_session.exec = AsyncMock(return_value=exec_result)

    result = await _resolve_files_for_sources(session=mock_session, user_id=1, allowed_sources=["doesnt-exist.pdf"])
    assert result == []


def _make_retrieved_chunk(content: str, source_name: str = "docs.pdf") -> RetrievedChunk:
    return RetrievedChunk(
        source_name=source_name,
        chapter=None,
        section=None,
        subsection=None,
        content=content,
    )


def test_format_context_groups_by_source_and_labels_sections() -> None:
    from app.core_plugins.slack.rag import _format_context

    chunks = [
        RetrievedChunk(source_name="a.pdf", chapter="Ch1", section="S1", subsection=None, content="text A"),
        RetrievedChunk(source_name="b.pdf", chapter=None, section=None, subsection=None, content="text B"),
        RetrievedChunk(source_name="a.pdf", chapter=None, section=None, subsection=None, content="text A2"),
    ]
    result = _format_context(chunks)

    assert "[DOCUMENT CONTEXT: a.pdf]" in result
    assert "[DOCUMENT CONTEXT: b.pdf]" in result
    assert "Ch1 / S1" in result  # partial-field section label
    assert "General" in result  # all-None fallback label
    assert result.index("a.pdf") < result.index("b.pdf")  # insertion order preserved
    assert "--- Excerpt 1" in result
    assert "--- Excerpt 2" in result  # a.pdf grouped two chunks


@pytest.mark.asyncio
async def test_answer_question_returns_no_files_response_when_no_files_resolved() -> None:
    config = SlackConfig(allowed_sources=["nope.pdf"])
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with patch("app.core_plugins.slack.rag._resolve_files_for_sources", new_callable=AsyncMock) as resolver:
        resolver.return_value = []
        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="q", config=config, agent_llm=agent_llm
        )

    assert response_type == ResponseType.no_files_resolved
    assert answer == NO_FILES_RESOLVED_MESSAGE


@pytest.mark.asyncio
async def test_answer_question_returns_file_not_found_on_drive_file_not_found_error() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with (
        patch("app.core_plugins.slack.rag._resolve_files_for_sources", new_callable=AsyncMock) as resolver,
        patch("app.core_plugins.slack.rag.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
    ):
        resolver.return_value = [10]
        mock_retrieve.side_effect = DriveFileNotFoundError("missing")
        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="q", config=config, agent_llm=agent_llm
        )

    assert answer == DRIVE_FILE_NOT_FOUND_MESSAGE
    assert response_type == ResponseType.drive_file_not_found


@pytest.mark.asyncio
async def test_answer_question_returns_not_ready_on_rag_not_ready_error() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with (
        patch("app.core_plugins.slack.rag._resolve_files_for_sources", new_callable=AsyncMock) as resolver,
        patch("app.core_plugins.slack.rag.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
    ):
        resolver.return_value = [10]
        mock_retrieve.side_effect = RAGNotReadyError(file_db_id=10, rag_status="processing")
        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="q", config=config, agent_llm=agent_llm
        )

    assert answer == RAG_NOT_READY_MESSAGE
    assert response_type == ResponseType.rag_not_ready


@pytest.mark.asyncio
async def test_answer_question_returns_retrieval_error_on_rag_retrieval_error() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with (
        patch("app.core_plugins.slack.rag._resolve_files_for_sources", new_callable=AsyncMock) as resolver,
        patch("app.core_plugins.slack.rag.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
    ):
        resolver.return_value = [10, 11]
        mock_retrieve.side_effect = RAGRetrievalError("agent error")
        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="q", config=config, agent_llm=agent_llm
        )

    assert response_type == ResponseType.retrieval_error
    assert answer == RETRIEVAL_ERROR_MESSAGE


@pytest.mark.asyncio
async def test_answer_question_returns_fallback_when_chunks_empty() -> None:
    config = SlackConfig(fallback_message="Nothing found.")
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with (
        patch("app.core_plugins.slack.rag._resolve_files_for_sources", new_callable=AsyncMock) as resolver,
        patch("app.core_plugins.slack.rag.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
    ):
        resolver.return_value = [10]
        mock_retrieve.return_value = []
        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="q", config=config, agent_llm=agent_llm
        )

    assert response_type == ResponseType.fallback
    assert answer == "Nothing found."


@pytest.mark.asyncio
async def test_answer_question_synthesizes_when_llm_provider_set() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()
    llm_provider = MagicMock()

    with (
        patch("app.core_plugins.slack.rag._resolve_files_for_sources", new_callable=AsyncMock) as resolver,
        patch("app.core_plugins.slack.rag.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
        patch("app.core_plugins.slack.rag.synthesize_answer", new_callable=AsyncMock) as synth,
    ):
        resolver.return_value = [10]
        mock_retrieve.return_value = [_make_retrieved_chunk("Loops repeat.", "docs.pdf")]
        synth.return_value = "Loops are constructs that repeat code."

        answer, response_type = await answer_question(
            session=mock_session,
            user_id=1,
            question="what are loops?",
            config=config,
            agent_llm=agent_llm,
            llm_provider=llm_provider,
        )

    assert response_type == ResponseType.rag_match
    assert answer == "Loops are constructs that repeat code."
    synth.assert_awaited_once()


@pytest.mark.asyncio
async def test_answer_question_returns_raw_chunks_when_no_synthesis_llm() -> None:
    """Without llm_provider, the answer contains the RAG-found prefix and chunk content."""
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with (
        patch("app.core_plugins.slack.rag._resolve_files_for_sources", new_callable=AsyncMock) as resolver,
        patch("app.core_plugins.slack.rag.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
    ):
        resolver.return_value = [10]
        mock_retrieve.return_value = [_make_retrieved_chunk("Recursion calls itself.", "docs.pdf")]
        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="recursion?", config=config, agent_llm=agent_llm
        )

    assert response_type == ResponseType.rag_match
    assert "AI summary is not available" in answer
    assert "Recursion calls itself." in answer


@pytest.mark.asyncio
async def test_answer_question_falls_back_to_raw_chunks_on_synthesis_error() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()
    llm_provider = MagicMock()

    with (
        patch("app.core_plugins.slack.rag._resolve_files_for_sources", new_callable=AsyncMock) as resolver,
        patch("app.core_plugins.slack.rag.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
        patch("app.core_plugins.slack.rag.synthesize_answer", new_callable=AsyncMock) as synth,
    ):
        resolver.return_value = [10]
        mock_retrieve.return_value = [_make_retrieved_chunk("Loops repeat.", "docs.pdf")]
        synth.side_effect = LangChainException("rate limit")

        answer, response_type = await answer_question(
            session=mock_session,
            user_id=1,
            question="what are loops?",
            config=config,
            agent_llm=agent_llm,
            llm_provider=llm_provider,
        )

    assert response_type == ResponseType.rag_match
    assert "Loops repeat." in answer
    assert "Could not generate" in answer
