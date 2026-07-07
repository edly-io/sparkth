"""Unit tests for Slack RAG dispatch."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import LangChainException

from sparkth.core_plugins.slack.config import SlackConfig, get_slack_settings
from sparkth.core_plugins.slack.constants import (
    DRIVE_FILE_NOT_FOUND_MESSAGE,
    NO_FILES_RESOLVED_MESSAGE,
    RAG_NOT_READY_MESSAGE,
    RETRIEVAL_ERROR_MESSAGE,
)
from sparkth.core_plugins.slack.enums import ResponseType
from sparkth.core_plugins.slack.rag import (
    _resolve_document_ids_for_sources,
    answer_question,
)
from sparkth.lib.documents import Document, DocumentStatus
from sparkth.lib.rag import (
    DocumentNotFoundError,
    RAGNotReadyError,
    RAGRetrievalError,
    RetrievedChunk,
    format_document_chunks_as_llm_context,
)


def _make_document(
    *,
    id: int = 1,
    user_id: int = 1,
    name: str = "doc.pdf",
    mime_type: str | None = "application/pdf",
    is_deleted: bool = False,
) -> Document:
    return Document(
        id=id,
        user_id=user_id,
        name=name,
        mime_type=mime_type,
        status=DocumentStatus.READY,
        is_deleted=is_deleted,
    )


@pytest.mark.asyncio
async def test_resolve_document_ids_for_sources_filters_by_allowed_sources() -> None:
    """Returns only Document IDs whose source_name is in allowed_sources."""
    mock_session = AsyncMock()
    exec_result = MagicMock()
    exec_result.all.return_value = [
        _make_document(id=100, name="python.pdf"),
        _make_document(id=101, name="ai.pdf"),
    ]
    mock_session.exec = AsyncMock(return_value=exec_result)

    result = await _resolve_document_ids_for_sources(
        mock_session,
        1,
        ["python.pdf", "ai.pdf"],
    )
    assert sorted(result) == [100, 101]


@pytest.mark.asyncio
async def test_resolve_document_ids_for_sources_empty_returns_capped_owner_documents() -> None:
    """When allowed_sources is empty, returns up to max_agent_files owner document_ids ordered by id ASC."""
    mock_session = AsyncMock()
    mock_documents = [_make_document(id=i * 10, name=f"doc-{i}.pdf") for i in range(1, 9)]
    exec_result = MagicMock()
    exec_result.all.return_value = mock_documents
    mock_session.exec = AsyncMock(return_value=exec_result)

    result = await _resolve_document_ids_for_sources(mock_session, 1, [])
    assert result == [10, 20, 30, 40, 50]
    assert len(result) == get_slack_settings().max_agent_files


@pytest.mark.asyncio
async def test_resolve_document_ids_for_sources_returns_empty_when_no_documents() -> None:
    mock_session = AsyncMock()
    exec_result = MagicMock()
    exec_result.all.return_value = []
    mock_session.exec = AsyncMock(return_value=exec_result)

    result = await _resolve_document_ids_for_sources(mock_session, 1, ["doesnt-exist.pdf"])
    assert result == []


def _make_retrieved_chunk(content: str, source_name: str = "docs.pdf") -> RetrievedChunk:
    return RetrievedChunk(
        source_name=source_name,
        chapter=None,
        section=None,
        subsection=None,
        content=content,
    )


def test_format_document_chunks_as_llm_context_renders_header_and_excerpts() -> None:
    chunks = [
        RetrievedChunk(source_name="a.pdf", chapter="Ch1", section="S1", subsection=None, content="text A"),
        RetrievedChunk(source_name="a.pdf", chapter=None, section=None, subsection=None, content="text A2"),
    ]
    result = format_document_chunks_as_llm_context(chunks)
    assert "[DOCUMENT CONTEXT: a.pdf]" in result
    assert "Ch1 / S1" in result
    assert "General" in result
    assert "--- Excerpt 1" in result
    assert "--- Excerpt 2" in result


@pytest.mark.asyncio
async def test_answer_question_returns_no_files_response_when_no_files_resolved() -> None:
    config = SlackConfig(allowed_sources=["nope.pdf"])
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with patch("sparkth.core_plugins.slack.rag._resolve_document_ids_for_sources", new_callable=AsyncMock) as resolver:
        resolver.return_value = []
        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="q", config=config, agent_llm=agent_llm
        )

    assert response_type == ResponseType.NO_FILES_RESOLVED
    assert answer == NO_FILES_RESOLVED_MESSAGE


@pytest.mark.asyncio
async def test_answer_question_returns_file_not_found_on_drive_file_not_found_error() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with (
        patch("sparkth.core_plugins.slack.rag._resolve_document_ids_for_sources", new_callable=AsyncMock) as resolver,
        patch("sparkth.core_plugins.slack.rag.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
    ):
        resolver.return_value = [10]
        mock_retrieve.side_effect = DocumentNotFoundError("missing")
        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="q", config=config, agent_llm=agent_llm
        )

    assert answer == DRIVE_FILE_NOT_FOUND_MESSAGE
    assert response_type == ResponseType.DRIVE_FILE_NOT_FOUND


@pytest.mark.asyncio
async def test_answer_question_returns_not_ready_on_rag_not_ready_error() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with (
        patch("sparkth.core_plugins.slack.rag._resolve_document_ids_for_sources", new_callable=AsyncMock) as resolver,
        patch("sparkth.core_plugins.slack.rag.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
    ):
        resolver.return_value = [10]
        mock_retrieve.side_effect = RAGNotReadyError(10, "processing")
        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="q", config=config, agent_llm=agent_llm
        )

    assert answer == RAG_NOT_READY_MESSAGE
    assert response_type == ResponseType.RAG_NOT_READY


@pytest.mark.asyncio
async def test_answer_question_returns_retrieval_error_on_rag_retrieval_error() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with (
        patch("sparkth.core_plugins.slack.rag._resolve_document_ids_for_sources", new_callable=AsyncMock) as resolver,
        patch("sparkth.core_plugins.slack.rag.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
    ):
        resolver.return_value = [10, 11]
        mock_retrieve.side_effect = RAGRetrievalError("agent error")
        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="q", config=config, agent_llm=agent_llm
        )

    assert response_type == ResponseType.RETRIEVAL_ERROR
    assert answer == RETRIEVAL_ERROR_MESSAGE


@pytest.mark.asyncio
async def test_answer_question_returns_fallback_when_chunks_empty() -> None:
    config = SlackConfig(fallback_message="Nothing found.")
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with (
        patch("sparkth.core_plugins.slack.rag._resolve_document_ids_for_sources", new_callable=AsyncMock) as resolver,
        patch("sparkth.core_plugins.slack.rag.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
    ):
        resolver.return_value = [10]
        mock_retrieve.return_value = []
        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="q", config=config, agent_llm=agent_llm
        )

    assert response_type == ResponseType.FALLBACK
    assert answer == "Nothing found."


@pytest.mark.asyncio
async def test_answer_question_synthesizes_when_llm_provider_set() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()
    llm_provider = MagicMock()

    with (
        patch("sparkth.core_plugins.slack.rag._resolve_document_ids_for_sources", new_callable=AsyncMock) as resolver,
        patch("sparkth.core_plugins.slack.rag.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
        patch("sparkth.core_plugins.slack.rag.synthesize_answer", new_callable=AsyncMock) as synth,
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

    assert response_type == ResponseType.RAG_MATCH
    assert answer == "Loops are constructs that repeat code."
    synth.assert_awaited_once()


@pytest.mark.asyncio
async def test_answer_question_returns_raw_chunks_when_no_synthesis_llm() -> None:
    """Without llm_provider, the answer contains the RAG-found prefix and chunk content."""
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with (
        patch("sparkth.core_plugins.slack.rag._resolve_document_ids_for_sources", new_callable=AsyncMock) as resolver,
        patch("sparkth.core_plugins.slack.rag.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
    ):
        resolver.return_value = [10]
        mock_retrieve.return_value = [_make_retrieved_chunk("Recursion calls itself.", "docs.pdf")]
        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="recursion?", config=config, agent_llm=agent_llm
        )

    assert response_type == ResponseType.RAG_MATCH
    assert "AI summary is not available" in answer
    assert "Recursion calls itself." in answer


@pytest.mark.asyncio
async def test_answer_question_falls_back_to_raw_chunks_on_synthesis_error() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()
    llm_provider = MagicMock()

    with (
        patch("sparkth.core_plugins.slack.rag._resolve_document_ids_for_sources", new_callable=AsyncMock) as resolver,
        patch("sparkth.core_plugins.slack.rag.agentic_retrieve_context", new_callable=AsyncMock) as mock_retrieve,
        patch("sparkth.core_plugins.slack.rag.synthesize_answer", new_callable=AsyncMock) as synth,
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

    assert response_type == ResponseType.RAG_MATCH
    assert "Loops repeat." in answer
    assert "Could not generate" in answer
