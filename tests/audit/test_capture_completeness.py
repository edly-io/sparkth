"""ADR-0002 completeness test: every tool-execution entry point in the
codebase must be audited, so new execution paths cannot appear silently.
Structural checks cover the known seams: the ``Tool`` hook dataclass and the
FastMCP server go through the audited wrapper, while LangChain-executed agent
tools are covered by the process-global callback handler. A source scan pins
the set of modules allowed to construct executable tools at all."""

from pathlib import Path
from typing import Any

from langchain_core.callbacks.manager import AsyncCallbackManager

import sparkth
from sparkth.lib.audit.callbacks import AuditToolCallbackHandler
from sparkth.lib.mcp.hooks import Tool, generate_input_schema
from sparkth.mcp.server import mcp
from sparkth.rag.mcp.agent_tools import build_search_tools

SPARKTH_ROOT = Path(sparkth.__file__).parent


def _is_audited(handler: Any) -> bool:
    return getattr(handler, "__audit_wrapped__", False) is True


async def dummy_handler(course_id: int, name: str = "x") -> str:
    """A handler for exercising Tool wrapping."""
    return name


class TestToolHookWrapsHandlers:
    """Every ``Tool`` on the MCP_TOOLS hook is audited by construction, which
    covers the FastMCP server and the chat ToolRegistry at once (both execute
    ``Tool.handler``)."""

    def test_tool_handler_is_wrapped_at_construction(self) -> None:
        tool = Tool(dummy_handler)
        assert _is_audited(tool.handler)

    def test_wrapping_preserves_name_description_and_schema(self) -> None:
        tool = Tool(dummy_handler)
        assert tool.name == "dummy_handler"
        assert tool.description == "A handler for exercising Tool wrapping."
        assert tool.input_schema == generate_input_schema(dummy_handler)


class TestFastMCPServerCoverage:
    async def test_every_registered_server_tool_is_audited(self) -> None:
        """Covers tools registered directly on the server (bypassing the
        MCP_TOOLS hook), e.g. get_course_generation_prompt_tool."""
        tools = await mcp.get_tools()
        assert tools, "expected at least the course-generation tool"
        # FunctionTool.fn is the registered callable; getattr keeps the check
        # honest for any future tool subclass without a wrapped function.
        unaudited = [name for name, tool in tools.items() if not _is_audited(getattr(tool, "fn", None))]
        assert unaudited == []

    def test_server_records_protocol_level_failures(self) -> None:
        """Calls that never reach a handler (unknown tool, input validation)
        must still leave a failure record: the server carries the audit
        middleware as a backstop."""
        from sparkth.mcp.audit import ToolCallAuditMiddleware

        assert any(isinstance(m, ToolCallAuditMiddleware) for m in mcp.middleware)


class TestLangChainExecutionCoverage:
    """In-process agent tools (the RAG search agent's, and any future ones)
    are plain coroutines: their executions are recorded by the process-global
    LangChain callback handler, active by default, not by per-tool wrapping.
    tests/audit/test_langchain_callback.py exercises the recording itself;
    tests/rag/mcp/test_agent_tools_audit.py exercises it through a RAG tool."""

    def test_audit_callback_handler_is_active_by_default(self) -> None:
        manager = AsyncCallbackManager.configure()
        assert any(isinstance(handler, AuditToolCallbackHandler) for handler in manager.inheritable_handlers)

    def test_rag_search_tools_rely_on_the_callback_not_wrapping(self) -> None:
        """The decorators are gone on purpose; if per-tool wrapping returns,
        runs would be double-recorded (wrapper plus untagged callback run)."""
        tools = build_search_tools(document_id=1)
        assert tools
        assert [tool.name for tool in tools if _is_audited(tool.coroutine)] == []


class TestNoUnauditedConstructionSites:
    """Source-level guard: the only modules allowed to build executable tools
    are the audited seams. A new construction site must be wired through
    ``audited_tool`` and added here deliberately."""

    ALLOWED = {
        Path("plugins/chat/tools.py"),  # converts already-wrapped Tool.handler (tagged for the callback)
        Path("rag/mcp/agent_tools.py"),  # plain coroutines; runs recorded by the callback handler
        Path("rag/retrieval/agent.py"),  # consumes build_search_tools only
        Path("mcp/server.py"),  # direct @mcp.tool registrations, wrapped explicitly
    }

    MARKERS = ("StructuredTool(", "StructuredTool.from_function", "@mcp.tool", "create_agent(")

    def test_tool_construction_is_confined_to_audited_modules(self) -> None:
        offenders: list[str] = []
        for path in SPARKTH_ROOT.rglob("*.py"):
            relative = path.relative_to(SPARKTH_ROOT)
            if relative in self.ALLOWED or "tests" in relative.parts:
                continue
            source = path.read_text(encoding="utf-8")
            for marker in self.MARKERS:
                if marker in source:
                    offenders.append(f"{relative}: {marker}")
        assert offenders == []
