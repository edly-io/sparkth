"""Tests for RAG agent retrieval orchestration."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.exceptions import LangChainException
from langgraph.errors import GraphRecursionError
from pydantic import ValidationError

from sparkth.rag.exceptions import RAGRetrievalError
from sparkth.rag.retrieval.agent import _llm_model_info, run_agentic_rag_retrieval
from sparkth.rag.schemas import RAGSearchAgentResponse, SectionRef


class TestLLMModelInfo:
    """Model identity comes from LangChain's standardized tracing params."""

    def test_reads_provider_and_model_from_ls_params(self) -> None:
        from langchain_anthropic import ChatAnthropic
        from pydantic import SecretStr

        info = _llm_model_info(ChatAnthropic(anthropic_api_key=SecretStr("test"), model="claude-sonnet-5"))

        assert info is not None
        assert info.provider == "anthropic"
        assert info.name == "claude-sonnet-5"

    def test_records_langchain_provider_spelling_verbatim(self) -> None:
        """The provider is evidence of what actually ran, recorded as LangChain
        reports it (google_genai, not our registry's google)."""
        from langchain_google_genai import ChatGoogleGenerativeAI

        info = _llm_model_info(ChatGoogleGenerativeAI(google_api_key="test", model="gemini-2.5-pro"))

        assert info is not None
        assert info.provider == "google_genai"
        assert info.name == "gemini-2.5-pro"

    def test_returns_none_for_a_non_langchain_object(self) -> None:
        assert _llm_model_info(object()) is None


def _make_validation_error() -> ValidationError:
    try:
        RAGSearchAgentResponse.model_validate({"source_name": [], "selected_sections": "x"})
    except ValidationError as exc:
        return exc
    raise AssertionError("ValidationError not raised")


class TestRunRagSearch:
    """Tests for run_agentic_rag_retrieval covering structured response and error paths."""

    def _patch_agent(self, agent: Any) -> Any:
        return patch("sparkth.rag.retrieval.agent.create_agent", return_value=agent)

    def _patch_build_tools(self) -> Any:
        return patch("sparkth.rag.retrieval.agent.build_search_tools", return_value=[])

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
            result = await run_agentic_rag_retrieval(MagicMock(), 2, "intro")

        assert result.source_name == "doc.pdf"
        assert len(result.selected_sections) == 1
        assert result.selected_sections[0].section == "Introduction"

    @pytest.mark.asyncio
    async def test_missing_structured_response_returns_empty(self) -> None:
        agent = self._make_agent({"messages": []})

        with self._patch_build_tools(), self._patch_agent(agent):
            result = await run_agentic_rag_retrieval(MagicMock(), 2, "intro")

        assert result.source_name == ""
        assert result.selected_sections == []

    @pytest.mark.asyncio
    async def test_validation_error_raises_retrieval_error(self) -> None:
        agent = MagicMock()
        agent.ainvoke = AsyncMock(side_effect=_make_validation_error())

        with self._patch_build_tools(), self._patch_agent(agent):
            with pytest.raises(RAGRetrievalError):
                await run_agentic_rag_retrieval(MagicMock(), 2, "intro")

    @pytest.mark.asyncio
    async def test_langchain_exception_raises_retrieval_error(self) -> None:
        agent = MagicMock()
        agent.ainvoke = AsyncMock(side_effect=LangChainException("agent failed"))

        with self._patch_build_tools(), self._patch_agent(agent):
            with pytest.raises(RAGRetrievalError):
                await run_agentic_rag_retrieval(MagicMock(), 2, "intro")

    @pytest.mark.asyncio
    async def test_graph_recursion_error_raises_retrieval_error(self) -> None:
        agent = MagicMock()
        agent.ainvoke = AsyncMock(side_effect=GraphRecursionError())

        with self._patch_build_tools(), self._patch_agent(agent):
            with pytest.raises(RAGRetrievalError, match="maximum steps"):
                await run_agentic_rag_retrieval(MagicMock(), 2, "intro")

    @pytest.mark.asyncio
    async def test_value_error_propagates(self) -> None:
        agent = MagicMock()
        agent.ainvoke = AsyncMock(side_effect=ValueError("unexpected"))

        with self._patch_build_tools(), self._patch_agent(agent):
            with pytest.raises(ValueError):
                await run_agentic_rag_retrieval(MagicMock(), 2, "intro")
