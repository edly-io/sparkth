"""Tests for get_context_via_agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.rag.context_service import RAGContext
from app.rag.enums import RagStatus
from app.rag.exceptions import DriveFileNotFoundError, RAGNotReadyError, RAGRetrievalError
from app.rag.retrieval.agent import get_context_via_agent
from app.rag.schemas import RAGSearchAgentResponse, SectionRef


class TestGetContextViaAgent:
    """Test get_context_via_agent function."""

    @pytest.mark.asyncio
    async def test_happy_path_uses_agent_sections(self) -> None:
        """Agent-selected sections are passed directly to fetch_chunks_by_sections."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "bio.pdf"
        mock_file.rag_status = RagStatus.READY

        selected = [SectionRef(chapter=None, section="Photosynthesis", subsection=None)]

        mock_result = MagicMock()
        mock_result.chunk.id = 1
        mock_result.chunk.content = "Test content"
        mock_result.chunk.chapter = None
        mock_result.chunk.section = "Photosynthesis"
        mock_result.chunk.subsection = None
        mock_result.similarity = 1.0

        mock_store = MagicMock()
        mock_store.fetch_chunks_by_sections = AsyncMock(return_value=[mock_result])

        with (
            patch("app.rag.context_service._lookup_drive_file", return_value=mock_file),
            patch("app.rag.retrieval.agent.run_agentic_rag_retrieval", new_callable=AsyncMock) as mock_agent,
            patch("app.rag.retrieval.agent.ChunkStoreService", return_value=mock_store),
        ):
            mock_agent.return_value = RAGSearchAgentResponse(
                source_name="bio.pdf",
                selected_sections=selected,
            )

            result = await get_context_via_agent(
                session=mock_session,
                user_id=1,
                file_db_id=1,
                query="test",
                llm=MagicMock(),
            )

        assert isinstance(result, RAGContext)
        assert result.source_name == "bio.pdf"
        assert len(result.chunks) == 1
        mock_store.fetch_chunks_by_sections.assert_awaited_once()
        call_kwargs = mock_store.fetch_chunks_by_sections.call_args.kwargs
        assert call_kwargs["section_keys"] == [s.model_dump() for s in selected]

    @pytest.mark.asyncio
    async def test_empty_sections_returns_no_chunks(self) -> None:
        """When agent returns no sections, fetch_chunks_by_sections returns empty."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "test.pdf"
        mock_file.rag_status = RagStatus.READY

        mock_store = MagicMock()
        mock_store.fetch_chunks_by_sections = AsyncMock(return_value=[])

        with (
            patch("app.rag.context_service._lookup_drive_file", return_value=mock_file),
            patch("app.rag.retrieval.agent.run_agentic_rag_retrieval", new_callable=AsyncMock) as mock_agent,
            patch("app.rag.retrieval.agent.ChunkStoreService", return_value=mock_store),
        ):
            mock_agent.return_value = RAGSearchAgentResponse(
                source_name="test.pdf",
                selected_sections=[],
            )

            result = await get_context_via_agent(
                session=mock_session,
                user_id=1,
                file_db_id=1,
                query="test",
                llm=MagicMock(),
            )

        assert result.chunks == []
        mock_store.fetch_chunks_by_sections.assert_awaited_once()
        call_kwargs = mock_store.fetch_chunks_by_sections.call_args.kwargs
        assert call_kwargs["section_keys"] == []

    @pytest.mark.asyncio
    async def test_file_not_found_raises_drive_file_not_found_error(self) -> None:
        """Missing file raises DriveFileNotFoundError."""
        mock_session = AsyncMock(spec=AsyncSession)

        with patch("app.rag.context_service._lookup_drive_file") as mock_lookup:
            mock_lookup.side_effect = DriveFileNotFoundError("Not found")

            with pytest.raises(DriveFileNotFoundError):
                await get_context_via_agent(
                    session=mock_session,
                    user_id=1,
                    file_db_id=999,
                    query="test",
                    llm=MagicMock(),
                )

    @pytest.mark.asyncio
    async def test_rag_not_ready_raises(self) -> None:
        """RAGNotReadyError is raised when file is not ready."""
        mock_session = AsyncMock(spec=AsyncSession)

        with patch("app.rag.context_service._lookup_drive_file") as mock_lookup:
            mock_lookup.side_effect = RAGNotReadyError(1, "processing")

            with pytest.raises(RAGNotReadyError):
                await get_context_via_agent(
                    session=mock_session,
                    user_id=1,
                    file_db_id=1,
                    query="test",
                    llm=MagicMock(),
                )

    @pytest.mark.asyncio
    async def test_agent_error_raises_retrieval_error(self) -> None:
        """Agent errors raise RAGRetrievalError."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "test.pdf"
        mock_file.rag_status = RagStatus.READY

        with (
            patch("app.rag.context_service._lookup_drive_file", return_value=mock_file),
            patch("app.rag.retrieval.agent.run_agentic_rag_retrieval", new_callable=AsyncMock) as mock_agent,
        ):
            mock_agent.side_effect = RAGRetrievalError("Agent failed")

            with pytest.raises(RAGRetrievalError):
                await get_context_via_agent(
                    session=mock_session,
                    user_id=1,
                    file_db_id=1,
                    query="test",
                    llm=MagicMock(),
                )

    @pytest.mark.asyncio
    async def test_section_fetch_error_raises_retrieval_error(self) -> None:
        """SQLAlchemyError from fetch_chunks_by_sections raises RAGRetrievalError."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "test.pdf"
        mock_file.rag_status = RagStatus.READY

        mock_store = MagicMock()
        mock_store.fetch_chunks_by_sections = AsyncMock(side_effect=SQLAlchemyError("DB error"))

        with (
            patch("app.rag.context_service._lookup_drive_file", return_value=mock_file),
            patch("app.rag.retrieval.agent.run_agentic_rag_retrieval", new_callable=AsyncMock) as mock_agent,
            patch("app.rag.retrieval.agent.ChunkStoreService", return_value=mock_store),
        ):
            mock_agent.return_value = RAGSearchAgentResponse(
                source_name="test.pdf",
                selected_sections=[SectionRef(chapter=None, section="Section A", subsection=None)],
            )

            with pytest.raises(RAGRetrievalError):
                await get_context_via_agent(
                    session=mock_session,
                    user_id=1,
                    file_db_id=1,
                    query="test",
                    llm=MagicMock(),
                )

    @pytest.mark.asyncio
    async def test_empty_query_falls_back_to_source_name(self) -> None:
        """Empty query is replaced with source_name before calling the agent."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "test.pdf"
        mock_file.rag_status = RagStatus.READY

        mock_store = MagicMock()
        mock_store.fetch_chunks_by_sections = AsyncMock(return_value=[])

        with (
            patch("app.rag.context_service._lookup_drive_file", return_value=mock_file),
            patch("app.rag.retrieval.agent.run_agentic_rag_retrieval", new_callable=AsyncMock) as mock_agent,
            patch("app.rag.retrieval.agent.ChunkStoreService", return_value=mock_store),
        ):
            mock_agent.return_value = RAGSearchAgentResponse(
                source_name="test.pdf",
                selected_sections=[],
            )

            await get_context_via_agent(
                session=mock_session,
                user_id=1,
                file_db_id=1,
                query="",
                llm=MagicMock(),
            )

            mock_agent.assert_called_once()
            call_kwargs = mock_agent.call_args.kwargs
            assert call_kwargs["user_query"] == "test.pdf"
