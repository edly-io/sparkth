"""Tests for get_context_via_agent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.rag.exceptions import DocumentNotFoundError, RAGNotReadyError, RAGRetrievalError
from app.rag.models import DocumentChunk
from app.rag.retrieval.agent import get_context_via_agent
from app.rag.schemas import RAGSearchAgentResponse, SectionRef
from app.rag.types import RAGContext


class TestGetContextViaAgent:
    """Test get_context_via_agent function."""

    @pytest.mark.asyncio
    async def test_happy_path_uses_agent_sections(self) -> None:
        """Agent-selected sections are passed directly to fetch_chunks_by_sections."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_doc = MagicMock()
        mock_doc.id = 1
        mock_doc.name = "bio.pdf"

        selected = [SectionRef(chapter=None, section="Photosynthesis", subsection=None)]

        mock_chunk = DocumentChunk(
            id=1,
            source_name="bio.pdf",
            content="Test content",
            chapter=None,
            section="Photosynthesis",
            subsection=None,
        )

        mock_store = MagicMock()
        mock_store.fetch_chunks_by_sections = AsyncMock(return_value=[mock_chunk])

        with (
            patch("app.rag.retrieval.agent._lookup_document", return_value=mock_doc),
            patch("app.rag.retrieval.agent.run_agentic_rag_retrieval", new_callable=AsyncMock) as mock_agent,
            patch("app.rag.retrieval.agent.ChunkStoreService", return_value=mock_store),
        ):
            mock_agent.return_value = RAGSearchAgentResponse(
                source_name="bio.pdf",
                selected_sections=selected,
            )

            result = await get_context_via_agent(
                session=mock_session,
                document_id=1,
                query="test",
                llm=MagicMock(),
            )

        assert isinstance(result, RAGContext)
        assert result.source_name == "bio.pdf"
        assert len(result.chunks) == 1
        mock_store.fetch_chunks_by_sections.assert_awaited_once()
        assert mock_store.fetch_chunks_by_sections.call_args.args[2] == [s.model_dump() for s in selected]

    @pytest.mark.asyncio
    async def test_empty_sections_returns_no_chunks(self) -> None:
        """When agent returns no sections, fetch_chunks_by_sections returns empty."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_doc = MagicMock()
        mock_doc.id = 1
        mock_doc.name = "test.pdf"

        mock_store = MagicMock()
        mock_store.fetch_chunks_by_sections = AsyncMock(return_value=[])

        with (
            patch("app.rag.retrieval.agent._lookup_document", return_value=mock_doc),
            patch("app.rag.retrieval.agent.run_agentic_rag_retrieval", new_callable=AsyncMock) as mock_agent,
            patch("app.rag.retrieval.agent.ChunkStoreService", return_value=mock_store),
        ):
            mock_agent.return_value = RAGSearchAgentResponse(
                source_name="test.pdf",
                selected_sections=[],
            )

            result = await get_context_via_agent(
                session=mock_session,
                document_id=1,
                query="test",
                llm=MagicMock(),
            )

        assert result.chunks == []
        mock_store.fetch_chunks_by_sections.assert_awaited_once()
        assert mock_store.fetch_chunks_by_sections.call_args.args[2] == []

    @pytest.mark.asyncio
    async def test_document_not_found_raises_error(self) -> None:
        """Missing document raises DocumentNotFoundError."""
        mock_session = AsyncMock(spec=AsyncSession)

        with patch("app.rag.retrieval.agent._lookup_document") as mock_lookup:
            mock_lookup.side_effect = DocumentNotFoundError("Not found")

            with pytest.raises(DocumentNotFoundError):
                await get_context_via_agent(
                    session=mock_session,
                    document_id=999,
                    query="test",
                    llm=MagicMock(),
                )

    @pytest.mark.asyncio
    async def test_rag_not_ready_raises(self) -> None:
        """RAGNotReadyError is raised when document is not ready."""
        mock_session = AsyncMock(spec=AsyncSession)

        with patch("app.rag.retrieval.agent._lookup_document") as mock_lookup:
            mock_lookup.side_effect = RAGNotReadyError(1, "processing")

            with pytest.raises(RAGNotReadyError):
                await get_context_via_agent(
                    session=mock_session,
                    document_id=1,
                    query="test",
                    llm=MagicMock(),
                )

    @pytest.mark.asyncio
    async def test_agent_error_raises_retrieval_error(self) -> None:
        """Agent errors raise RAGRetrievalError."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_doc = MagicMock()
        mock_doc.id = 1
        mock_doc.name = "test.pdf"

        with (
            patch("app.rag.retrieval.agent._lookup_document", return_value=mock_doc),
            patch("app.rag.retrieval.agent.run_agentic_rag_retrieval", new_callable=AsyncMock) as mock_agent,
        ):
            mock_agent.side_effect = RAGRetrievalError("Agent failed")

            with pytest.raises(RAGRetrievalError):
                await get_context_via_agent(
                    session=mock_session,
                    document_id=1,
                    query="test",
                    llm=MagicMock(),
                )

    @pytest.mark.asyncio
    async def test_section_fetch_error_raises_retrieval_error(self) -> None:
        """SQLAlchemyError from fetch_chunks_by_sections raises RAGRetrievalError."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_doc = MagicMock()
        mock_doc.id = 1
        mock_doc.name = "test.pdf"

        mock_store = MagicMock()
        mock_store.fetch_chunks_by_sections = AsyncMock(side_effect=SQLAlchemyError("DB error"))

        with (
            patch("app.rag.retrieval.agent._lookup_document", return_value=mock_doc),
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
                    document_id=1,
                    query="test",
                    llm=MagicMock(),
                )

    @pytest.mark.asyncio
    async def test_empty_query_falls_back_to_source_name(self) -> None:
        """Empty query is replaced with source_name before calling the agent."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_doc = MagicMock()
        mock_doc.id = 1
        mock_doc.name = "test.pdf"

        mock_store = MagicMock()
        mock_store.fetch_chunks_by_sections = AsyncMock(return_value=[])

        with (
            patch("app.rag.retrieval.agent._lookup_document", return_value=mock_doc),
            patch("app.rag.retrieval.agent.run_agentic_rag_retrieval", new_callable=AsyncMock) as mock_agent,
            patch("app.rag.retrieval.agent.ChunkStoreService", return_value=mock_store),
        ):
            mock_agent.return_value = RAGSearchAgentResponse(
                source_name="test.pdf",
                selected_sections=[],
            )

            await get_context_via_agent(
                session=mock_session,
                document_id=1,
                query="",
                llm=MagicMock(),
            )

            mock_agent.assert_called_once()
            assert mock_agent.call_args.args[2] == "test.pdf"
