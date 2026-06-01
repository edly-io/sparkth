"""Unit tests for Slack RAG dispatch."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import LangChainException

from app.core_plugins.slack.config import SlackConfig, get_slack_system_config
from app.core_plugins.slack.constants import (
    DRIVE_FILE_NOT_FOUND_MESSAGE,
    NO_FILES_RESOLVED_MESSAGE,
    RAG_NOT_READY_MESSAGE,
    RETRIEVAL_ERROR_MESSAGE,
)
from app.core_plugins.slack.models import ResponseType
from app.core_plugins.slack.rag import (
    _resolve_files_for_sources,
    _run_agent_fan_out,
    answer_question,
)
from app.rag.exceptions import DriveFileNotFoundError, RAGNotReadyError, RAGRetrievalError
from app.rag.store import SimilarityResult
from app.rag.types import RAGContext


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
    """When allowed_sources is empty, returns up to MAX_AGENT_FILES owner files ordered by id ASC."""
    mock_session = AsyncMock()
    mock_files = [MagicMock(id=i, name=f"doc-{i}.pdf", mime_type="application/pdf") for i in range(1, 9)]
    exec_result = MagicMock()
    exec_result.all.return_value = mock_files
    mock_session.exec = AsyncMock(return_value=exec_result)

    result = await _resolve_files_for_sources(session=mock_session, user_id=1, allowed_sources=[])
    assert result == [1, 2, 3, 4, 5]
    assert len(result) == get_slack_system_config().MAX_AGENT_FILES


@pytest.mark.asyncio
async def test_resolve_files_for_sources_returns_empty_when_no_files() -> None:
    mock_session = AsyncMock()
    exec_result = MagicMock()
    exec_result.all.return_value = []
    mock_session.exec = AsyncMock(return_value=exec_result)

    result = await _resolve_files_for_sources(session=mock_session, user_id=1, allowed_sources=["doesnt-exist.pdf"])
    assert result == []


def _make_rag_context(source: str = "docs.pdf", chunks: list[SimilarityResult] | None = None) -> RAGContext:
    return RAGContext(
        file_db_id=1,
        source_name=source,
        chunks=chunks if chunks is not None else [],
        formatted_text=f"[DOCUMENT CONTEXT: {source}]\nsome content",
    )


@pytest.mark.asyncio
async def test_fan_out_calls_agent_per_file_concurrently() -> None:
    """Each file_id triggers one get_context_via_agent call; gather is used."""
    agent_llm = MagicMock()

    with patch("app.core_plugins.slack.rag._rag_service") as mock_svc:
        mock_svc.get_context_via_agent = AsyncMock(side_effect=[_make_rag_context("a.pdf"), _make_rag_context("b.pdf")])
        results = await _run_agent_fan_out(
            user_id=42,
            file_ids=[10, 11],
            question="what is X?",
            agent_llm=agent_llm,
        )

    assert len(results) == 2
    assert {r.source_name for r in results} == {"a.pdf", "b.pdf"}
    assert mock_svc.get_context_via_agent.await_count == 2


@pytest.mark.asyncio
async def test_fan_out_propagates_rag_retrieval_error() -> None:
    """A per-file RAGRetrievalError is re-raised so the caller can translate it."""
    agent_llm = MagicMock()

    with patch("app.core_plugins.slack.rag._rag_service") as mock_svc:
        mock_svc.get_context_via_agent = AsyncMock(side_effect=RAGRetrievalError("MCP down"))
        with pytest.raises(RAGRetrievalError):
            await _run_agent_fan_out(
                user_id=42,
                file_ids=[10],
                question="test",
                agent_llm=agent_llm,
            )


@pytest.mark.asyncio
async def test_fan_out_returns_partial_results_when_some_files_fail() -> None:
    """When some files succeed and others fail, successful results are returned."""
    agent_llm = MagicMock()
    good_ctx = _make_rag_context("good.pdf")

    with patch("app.core_plugins.slack.rag._rag_service") as mock_svc:
        mock_svc.get_context_via_agent = AsyncMock(side_effect=[good_ctx, RAGRetrievalError("bad file")])
        results = await _run_agent_fan_out(
            user_id=42,
            file_ids=[10, 11],
            question="test",
            agent_llm=agent_llm,
        )

    assert len(results) == 1
    assert results[0].source_name == "good.pdf"


@pytest.mark.asyncio
async def test_fan_out_empty_file_ids_returns_empty() -> None:
    agent_llm = MagicMock()

    with patch("app.core_plugins.slack.rag._rag_service") as mock_svc:
        mock_svc.get_context_via_agent = AsyncMock()
        results = await _run_agent_fan_out(
            user_id=42,
            file_ids=[],
            question="test",
            agent_llm=agent_llm,
        )

    assert results == []
    mock_svc.get_context_via_agent.assert_not_awaited()


def _make_chunk(content: str, source_name: str = "docs.pdf") -> MagicMock:
    chunk = MagicMock()
    chunk.content = content
    chunk.chapter = None
    chunk.section = None
    chunk.subsection = None
    chunk.source_name = source_name
    return chunk


def _make_rag_context_with_chunks(source: str, chunk_texts: list[str]) -> RAGContext:
    results = [SimilarityResult(chunk=_make_chunk(t, source), similarity=1.0) for t in chunk_texts]
    return RAGContext(
        file_db_id=1,
        source_name=source,
        chunks=results,
        formatted_text=f"[DOCUMENT CONTEXT: {source}]\n" + "\n".join(chunk_texts),
    )


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

    assert response_type == ResponseType.NO_FILES_RESOLVED
    assert answer == NO_FILES_RESOLVED_MESSAGE


@pytest.mark.asyncio
async def test_answer_question_returns_fallback_when_all_contexts_empty() -> None:
    config = SlackConfig(fallback_message="Nothing found.")
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with (
        patch("app.core_plugins.slack.rag._resolve_files_for_sources", new_callable=AsyncMock) as resolver,
        patch("app.core_plugins.slack.rag._run_agent_fan_out", new_callable=AsyncMock) as fan_out,
    ):
        resolver.return_value = [10, 11]
        fan_out.return_value = [
            RAGContext(file_db_id=10, source_name="a.pdf", chunks=[], formatted_text=""),
            RAGContext(file_db_id=11, source_name="b.pdf", chunks=[], formatted_text=""),
        ]
        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="q", config=config, agent_llm=agent_llm
        )

    assert response_type == ResponseType.FALLBACK
    assert answer == "Nothing found."


@pytest.mark.asyncio
async def test_answer_question_returns_raw_chunks_when_no_synthesis_llm() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with (
        patch("app.core_plugins.slack.rag._resolve_files_for_sources", new_callable=AsyncMock) as resolver,
        patch("app.core_plugins.slack.rag._run_agent_fan_out", new_callable=AsyncMock) as fan_out,
    ):
        resolver.return_value = [10]
        fan_out.return_value = [_make_rag_context_with_chunks("docs.pdf", ["Recursion calls itself."])]
        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="recursion?", config=config, agent_llm=agent_llm
        )

    assert response_type == ResponseType.RAG_MATCH
    assert "Recursion calls itself." in answer


@pytest.mark.asyncio
async def test_answer_question_synthesizes_when_llm_provider_set() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()
    llm_provider = MagicMock()

    with (
        patch("app.core_plugins.slack.rag._resolve_files_for_sources", new_callable=AsyncMock) as resolver,
        patch("app.core_plugins.slack.rag._run_agent_fan_out", new_callable=AsyncMock) as fan_out,
        patch("app.core_plugins.slack.rag.synthesize_answer", new_callable=AsyncMock) as synth,
    ):
        resolver.return_value = [10]
        fan_out.return_value = [_make_rag_context_with_chunks("docs.pdf", ["Loops repeat."])]
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
async def test_answer_question_falls_back_to_raw_chunks_on_synthesis_error() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()
    llm_provider = MagicMock()

    with (
        patch("app.core_plugins.slack.rag._resolve_files_for_sources", new_callable=AsyncMock) as resolver,
        patch("app.core_plugins.slack.rag._run_agent_fan_out", new_callable=AsyncMock) as fan_out,
        patch("app.core_plugins.slack.rag.synthesize_answer", new_callable=AsyncMock) as synth,
    ):
        resolver.return_value = [10]
        fan_out.return_value = [_make_rag_context_with_chunks("docs.pdf", ["Loops repeat."])]
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


@pytest.mark.asyncio
async def test_answer_question_returns_retrieval_error_on_rag_retrieval_error() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with (
        patch("app.core_plugins.slack.rag._resolve_files_for_sources", new_callable=AsyncMock) as resolver,
        patch("app.core_plugins.slack.rag._run_agent_fan_out", new_callable=AsyncMock) as fan_out,
    ):
        resolver.return_value = [10, 11]
        fan_out.side_effect = RAGRetrievalError("agent error")

        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="q", config=config, agent_llm=agent_llm
        )

    assert response_type == ResponseType.RETRIEVAL_ERROR
    assert answer == RETRIEVAL_ERROR_MESSAGE


@pytest.mark.asyncio
async def test_answer_question_returns_not_ready_on_rag_not_ready_error() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with (
        patch("app.core_plugins.slack.rag._resolve_files_for_sources", new_callable=AsyncMock) as resolver,
        patch("app.core_plugins.slack.rag._run_agent_fan_out", new_callable=AsyncMock) as fan_out,
    ):
        resolver.return_value = [10]
        fan_out.side_effect = RAGNotReadyError(file_db_id=10, rag_status="processing")
        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="q", config=config, agent_llm=agent_llm
        )

    assert answer == RAG_NOT_READY_MESSAGE
    assert response_type == ResponseType.RAG_NOT_READY


@pytest.mark.asyncio
async def test_answer_question_returns_file_not_found_on_drive_file_not_found_error() -> None:
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with (
        patch("app.core_plugins.slack.rag._resolve_files_for_sources", new_callable=AsyncMock) as resolver,
        patch("app.core_plugins.slack.rag._run_agent_fan_out", new_callable=AsyncMock) as fan_out,
    ):
        resolver.return_value = [10]
        fan_out.side_effect = DriveFileNotFoundError("missing")
        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="q", config=config, agent_llm=agent_llm
        )

    assert answer == DRIVE_FILE_NOT_FOUND_MESSAGE
    assert response_type == ResponseType.DRIVE_FILE_NOT_FOUND


@pytest.mark.asyncio
async def test_answer_question_drops_empty_contexts_but_keeps_others() -> None:
    """When some files return zero chunks, the bot still answers from the rest."""
    config = SlackConfig()
    mock_session = AsyncMock()
    agent_llm = MagicMock()

    with (
        patch("app.core_plugins.slack.rag._resolve_files_for_sources", new_callable=AsyncMock) as resolver,
        patch("app.core_plugins.slack.rag._run_agent_fan_out", new_callable=AsyncMock) as fan_out,
    ):
        resolver.return_value = [10, 11]
        fan_out.return_value = [
            RAGContext(file_db_id=10, source_name="empty.pdf", chunks=[], formatted_text=""),
            _make_rag_context_with_chunks("good.pdf", ["Some content."]),
        ]
        answer, response_type = await answer_question(
            session=mock_session, user_id=1, question="q", config=config, agent_llm=agent_llm
        )

    assert response_type == ResponseType.RAG_MATCH
    assert "Some content." in answer
