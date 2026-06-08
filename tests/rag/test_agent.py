"""Tests for RAG agent."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import LangChainException
from langgraph.errors import GraphRecursionError
from pydantic import ValidationError

from app.rag.exceptions import RAGRetrievalError
from app.rag.retrieval.agent import run_agentic_rag_retrieval
from app.rag.schemas import RAGSearchAgentResponse, SectionRef


def _make_validation_error() -> ValidationError:
    try:
        RAGSearchAgentResponse.model_validate({"source_name": [], "selected_sections": "x"})
    except ValidationError as exc:
        return exc
    raise AssertionError("ValidationError not raised")


class TestRunRagSearch:
    """Tests for run_agentic_rag_retrieval covering the structured_response extraction and error paths."""

    def _patch_agent(self, agent: Any) -> Any:
        return patch("app.rag.retrieval.agent.create_agent", return_value=agent)

    def _patch_build_tools(self) -> Any:
        return patch("app.rag.retrieval.agent.build_search_tools", return_value=[])

    def _make_agent(self, return_value: dict[str, Any]) -> MagicMock:
        agent = MagicMock()
        agent.ainvoke = AsyncMock(return_value=return_value)
        return agent

    @pytest.mark.asyncio
    async def test_happy_path_returns_structured_response(self) -> None:
        expected = RAGSearchAgentResponse(
            source_name="doc.pdf",
            selected_sections=[SectionRef(section="Introduction")],
        )
        agent = self._make_agent({"structured_response": expected})

        with self._patch_build_tools(), self._patch_agent(agent):
            result = await run_agentic_rag_retrieval(MagicMock(), 1, 2, "intro")

        assert result.source_name == "doc.pdf"
        assert len(result.selected_sections) == 1
        assert result.selected_sections[0].section == "Introduction"

    @pytest.mark.asyncio
    async def test_missing_structured_response_returns_empty(self) -> None:
        agent = self._make_agent({"messages": []})

        with self._patch_build_tools(), self._patch_agent(agent):
            result = await run_agentic_rag_retrieval(MagicMock(), 1, 2, "intro")

        assert result.source_name == ""
        assert result.selected_sections == []

    @pytest.mark.asyncio
    async def test_validation_error_raises_retrieval_error(self) -> None:
        agent = MagicMock()
        agent.ainvoke = AsyncMock(side_effect=_make_validation_error())

        with self._patch_build_tools(), self._patch_agent(agent):
            with pytest.raises(RAGRetrievalError):
                await run_agentic_rag_retrieval(MagicMock(), 1, 2, "intro")

    @pytest.mark.asyncio
    async def test_langchain_exception_raises_retrieval_error(self) -> None:
        agent = MagicMock()
        agent.ainvoke = AsyncMock(side_effect=LangChainException("agent failed"))

        with self._patch_build_tools(), self._patch_agent(agent):
            with pytest.raises(RAGRetrievalError):
                await run_agentic_rag_retrieval(MagicMock(), 1, 2, "intro")

    @pytest.mark.asyncio
    async def test_graph_recursion_error_raises_retrieval_error(self) -> None:
        agent = MagicMock()
        agent.ainvoke = AsyncMock(side_effect=GraphRecursionError())

        with self._patch_build_tools(), self._patch_agent(agent):
            with pytest.raises(RAGRetrievalError, match="maximum steps"):
                await run_agentic_rag_retrieval(MagicMock(), 1, 2, "intro")

    @pytest.mark.asyncio
    async def test_value_error_propagates(self) -> None:
        agent = MagicMock()
        agent.ainvoke = AsyncMock(side_effect=ValueError("unexpected"))

        with self._patch_build_tools(), self._patch_agent(agent):
            with pytest.raises(ValueError):
                await run_agentic_rag_retrieval(MagicMock(), 1, 2, "intro")
