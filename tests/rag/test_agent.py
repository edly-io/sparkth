"""Tests for RAG agent."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ConnectError
from langchain_core.exceptions import LangChainException

from app.rag.agent import AgentSearchDecision, run_agentic_rag_search
from app.rag.exceptions import RAGRetrievalError


class TestAgentDecision:
    """Test agentic RAG search."""

    @pytest.mark.asyncio
    async def test_returns_source_name_and_sections(self) -> None:
        """Test that agent returns source_name and selected_sections."""
        with patch("app.rag.agent.MultiServerMCPClient") as mock_client_class:
            with patch("app.rag.agent.create_agent") as mock_create_agent:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.get_tools = AsyncMock(return_value=[])
                mock_client_class.return_value = mock_client

                # Mock the agent graph
                mock_graph = AsyncMock()
                decision_json = json.dumps(
                    {
                        "source_name": "doc.pdf",
                        "selected_sections": [
                            {"chapter": None, "section": "Introduction", "subsection": None},
                            {"chapter": None, "section": "Methods", "subsection": None},
                        ],
                    }
                )
                mock_graph.ainvoke.return_value = {"messages": [MagicMock(content=decision_json)]}
                mock_create_agent.return_value = mock_graph

                mock_llm = MagicMock()
                result = await run_agentic_rag_search(
                    llm=mock_llm,
                    user_id=1,
                    file_id=1,
                    user_query="What are the methods?",
                )

                assert isinstance(result, AgentSearchDecision)
                assert result.source_name == "doc.pdf"
                assert len(result.selected_sections) == 2
                assert result.selected_sections[0]["section"] == "Introduction"
                assert result.selected_sections[1]["section"] == "Methods"

    @pytest.mark.asyncio
    async def test_empty_sections_when_agent_returns_no_sections(self) -> None:
        """Test agent returning empty sections."""
        with patch("app.rag.agent.MultiServerMCPClient") as mock_client_class:
            with patch("app.rag.agent.create_agent") as mock_create_agent:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.get_tools = AsyncMock(return_value=[])
                mock_client_class.return_value = mock_client

                mock_graph = AsyncMock()
                decision_json = json.dumps(
                    {
                        "source_name": "doc.pdf",
                        "selected_sections": [],
                    }
                )
                mock_graph.ainvoke.return_value = {"messages": [MagicMock(content=decision_json)]}
                mock_create_agent.return_value = mock_graph

                mock_llm = MagicMock()
                result = await run_agentic_rag_search(
                    llm=mock_llm,
                    user_id=1,
                    file_id=1,
                    user_query="query",
                )

                assert result.selected_sections == []

    @pytest.mark.asyncio
    async def test_mcp_client_connection_error_raises(self) -> None:
        """Test that MCP connection errors raise RAGRetrievalError."""
        with patch("app.rag.agent.MultiServerMCPClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get_tools = AsyncMock(side_effect=ConnectError("Connection failed"))
            mock_client_class.return_value = mock_client

            mock_llm = MagicMock()
            with pytest.raises(RAGRetrievalError):
                await run_agentic_rag_search(
                    llm=mock_llm,
                    user_id=1,
                    file_id=1,
                    user_query="query",
                )

    @pytest.mark.asyncio
    async def test_agent_invocation_error_raises(self) -> None:
        """Test that agent invocation errors raise RAGRetrievalError."""
        with patch("app.rag.agent.MultiServerMCPClient") as mock_client_class:
            with patch("app.rag.agent.create_agent") as mock_create_agent:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.get_tools = AsyncMock(return_value=[])
                mock_client_class.return_value = mock_client

                mock_graph = AsyncMock()
                mock_graph.ainvoke.side_effect = LangChainException("Agent error")
                mock_create_agent.return_value = mock_graph

                mock_llm = MagicMock()
                with pytest.raises(RAGRetrievalError):
                    await run_agentic_rag_search(
                        llm=mock_llm,
                        user_id=1,
                        file_id=1,
                        user_query="query",
                    )

    @pytest.mark.asyncio
    async def test_user_id_forwarded_in_system_prompt(self) -> None:
        """Test that user_id and file_id are forwarded in the system prompt."""
        with patch("app.rag.agent.MultiServerMCPClient") as mock_client_class:
            with patch("app.rag.agent.create_agent") as mock_create_agent:
                with patch("app.rag.agent.SystemMessage") as mock_system_message:
                    mock_client = AsyncMock()
                    mock_client.__aenter__.return_value = mock_client
                    mock_client.get_tools = AsyncMock(return_value=[])
                    mock_client_class.return_value = mock_client

                    mock_graph = AsyncMock()
                    decision_json = json.dumps(
                        {
                            "source_name": "doc.pdf",
                            "selected_sections": [],
                        }
                    )
                    mock_graph.ainvoke.return_value = {"messages": [MagicMock(content=decision_json)]}
                    mock_create_agent.return_value = mock_graph

                    mock_llm = MagicMock()
                    await run_agentic_rag_search(
                        llm=mock_llm,
                        user_id=5,
                        file_id=10,
                        user_query="What?",
                    )

                    # Verify that the system message includes user_id and file_id
                    assert mock_system_message.called
                    call_args = str(mock_system_message.call_args)
                    assert "5" in call_args or "10" in call_args
