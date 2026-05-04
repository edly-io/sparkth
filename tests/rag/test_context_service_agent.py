"""Tests for RAG context service agent integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.rag.context_service import RAGContext, RAGContextService
from app.rag.exceptions import DriveFileNotFoundError, RAGNotReadyError, RAGRetrievalError
from app.rag.types import RAGSearchAgentResponse, RagStatus, SectionRef


class TestGetContextViaAgent:
    """Test get_context_via_agent method."""

    @pytest.mark.asyncio
    async def test_happy_path_uses_agent_sections(self) -> None:
        """Agent-selected sections are passed directly to fetch_chunks_by_sections."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "bio.pdf"
        mock_file.rag_status = RagStatus.READY

        selected = [SectionRef(chapter=None, section="Photosynthesis", subsection=None)]

        with patch.object(RAGContextService, "_lookup_drive_file", return_value=mock_file):
            with patch("app.rag.context_service.run_agentic_rag_search") as mock_agent:
                mock_agent.return_value = RAGSearchAgentResponse(
                    source_name="bio.pdf",
                    selected_sections=selected,
                )

                mock_result = MagicMock()
                mock_result.chunk.id = 1
                mock_result.chunk.content = "Test content"
                mock_result.chunk.chapter = None
                mock_result.chunk.section = "Photosynthesis"
                mock_result.chunk.subsection = None
                mock_result.similarity = 1.0

                mock_store = MagicMock()
                mock_store.fetch_chunks_by_sections = AsyncMock(return_value=[mock_result])

                service = RAGContextService()
                service._store = mock_store

                result = await service.get_context_via_agent(
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
                assert call_kwargs["section_keys"] == selected

    @pytest.mark.asyncio
    async def test_empty_sections_returns_no_chunks(self) -> None:
        """When agent returns no sections, fetch_chunks_by_sections returns empty."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "test.pdf"
        mock_file.rag_status = RagStatus.READY

        with patch.object(RAGContextService, "_lookup_drive_file", return_value=mock_file):
            with patch("app.rag.context_service.run_agentic_rag_search") as mock_agent:
                mock_agent.return_value = RAGSearchAgentResponse(
                    source_name="test.pdf",
                    selected_sections=[],
                )

                mock_store = MagicMock()
                mock_store.fetch_chunks_by_sections = AsyncMock(return_value=[])

                service = RAGContextService()
                service._store = mock_store

                result = await service.get_context_via_agent(
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

        with patch("app.rag.context_service.RAGContextService._lookup_drive_file") as mock_lookup:
            mock_lookup.side_effect = DriveFileNotFoundError("Not found")

            service = RAGContextService()

            with pytest.raises(DriveFileNotFoundError):
                await service.get_context_via_agent(
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

        with patch("app.rag.context_service.RAGContextService._lookup_drive_file") as mock_lookup:
            mock_lookup.side_effect = RAGNotReadyError(1, "processing")

            service = RAGContextService()

            with pytest.raises(RAGNotReadyError):
                await service.get_context_via_agent(
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

        with patch("app.rag.context_service.RAGContextService._lookup_drive_file") as mock_lookup:
            with patch("app.rag.context_service.run_agentic_rag_search") as mock_agent:
                mock_lookup.return_value = mock_file
                mock_agent.side_effect = RAGRetrievalError("Agent failed")

                service = RAGContextService()

                with pytest.raises(RAGRetrievalError):
                    await service.get_context_via_agent(
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

        with patch.object(RAGContextService, "_lookup_drive_file", return_value=mock_file):
            with patch("app.rag.context_service.run_agentic_rag_search") as mock_agent:
                mock_agent.return_value = RAGSearchAgentResponse(
                    source_name="test.pdf",
                    selected_sections=[SectionRef(chapter=None, section="Section A", subsection=None)],
                )

                mock_store = MagicMock()
                mock_store.fetch_chunks_by_sections = AsyncMock(side_effect=SQLAlchemyError("DB error"))

                service = RAGContextService()
                service._store = mock_store

                with pytest.raises(RAGRetrievalError):
                    await service.get_context_via_agent(
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

        with patch.object(RAGContextService, "_lookup_drive_file", return_value=mock_file):
            with patch("app.rag.context_service.run_agentic_rag_search") as mock_agent:
                mock_agent.return_value = RAGSearchAgentResponse(
                    source_name="test.pdf",
                    selected_sections=[],
                )

                mock_store = MagicMock()
                mock_store.fetch_chunks_by_sections = AsyncMock(return_value=[])

                service = RAGContextService()
                service._store = mock_store

                await service.get_context_via_agent(
                    session=mock_session,
                    user_id=1,
                    file_db_id=1,
                    query="",
                    llm=MagicMock(),
                )

                mock_agent.assert_called_once()
                call_kwargs = mock_agent.call_args.kwargs
                assert call_kwargs["user_query"] == "test.pdf"
