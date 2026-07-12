"""The RAG agent tools bypass ``Tool.handler`` (they are built as LangChain
``StructuredTool``s directly), so they are routed through the same audited
wrapper explicitly, and the agent runner stamps the ``rag`` source."""

from typing import Any
from unittest.mock import AsyncMock, patch

from sparkth.lib.testing import AuditEventsFetcher
from sparkth.rag.mcp.agent_tools import build_search_tools
from sparkth.rag.retrieval.agent import run_agentic_rag_retrieval
from sparkth.rag.schemas import RAGSearchAgentResponse


async def test_invoking_a_search_tool_records_the_execution(audit_events: AuditEventsFetcher) -> None:
    tool = next(t for t in build_search_tools(document_id=10) if t.name == "search_section_by_keyword")

    with patch("sparkth.rag.mcp.agent_tools.tools.search_section_by_keyword", new_callable=AsyncMock) as mock_fn:
        mock_fn.return_value = []
        await tool.ainvoke({"keyword": "intro"})

    invoked, completed = await audit_events()
    assert (invoked.category, invoked.action) == ("tool", "invoked")
    assert invoked.tool_name == "search_section_by_keyword"
    assert invoked.tool_args == {"keyword": "intro"}
    assert (completed.category, completed.action) == ("tool", "completed")


async def test_agent_run_stamps_rag_source_on_tool_events(audit_events: AuditEventsFetcher) -> None:
    """The agent runner installs a rag-source audit context, so tools executed
    inside the agent are attributed to the RAG surface."""
    tools_seen: dict[str, Any] = {}

    async def fake_ainvoke(payload: Any, config: Any = None) -> dict[str, Any]:
        tool = next(t for t in tools_seen["tools"] if t.name == "get_chunk_stats")
        with patch("sparkth.rag.mcp.agent_tools.tools.get_chunk_stats", new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = None
            await tool.ainvoke({})
        return {"structured_response": RAGSearchAgentResponse(source_name="doc", selected_sections=[])}

    def fake_create_agent(model: Any, tools: list[Any], response_format: Any, name: str) -> Any:
        tools_seen["tools"] = tools
        agent = AsyncMock()
        agent.ainvoke = fake_ainvoke
        return agent

    with patch("sparkth.rag.retrieval.agent.create_agent", side_effect=fake_create_agent):
        await run_agentic_rag_retrieval(llm=object(), document_id=3, user_query="stats?")

    rows = await audit_events()
    assert rows, "expected the in-agent tool call to be audited"
    assert all(row.source == "rag" for row in rows)
