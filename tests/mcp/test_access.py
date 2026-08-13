"""The plugin gate on the FastMCP server: a disabled plugin's tools stop being
callable and stop being advertised on ``/ai/mcp``.

The gate answers one question per request — is the plugin that contributed this
tool still switched on system-wide? It reads the flag from the database on every
call rather than at registration, because tools register once during the lifespan
while ``Plugin.enabled`` flips at runtime.

Each test drives a real FastMCP client against a server carrying the middleware,
so the whole chain is exercised: resolving which plugin owns the tool, the lookup
itself, and the rejection the caller sees.
"""

from types import SimpleNamespace
from typing import Any, cast

import mcp.types as mt
import pytest
from fastmcp import Client, FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import MiddlewareContext
from fastmcp.tools import ToolResult
from sqlalchemy.exc import OperationalError
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin
from sparkth.lib.audit import audited_tool
from sparkth.lib.mcp.hooks import Tool
from sparkth.lib.testing import AuditEventsFetcher
from sparkth.mcp.access import (
    PLUGIN_NAME_META_KEY,
    PluginToolAccessMiddleware,
    get_tool_plugin_name,
)
from sparkth.mcp.audit import ToolCallAuditMiddleware
from sparkth.mcp.server import _register_tool, mcp

PLUGIN_TOOL = "gated_tool"
CORE_TOOL = "ungated_tool"


async def echo(value: str) -> str:
    """A tool handler that exists only to be called."""
    return value


async def unreachable_call_next(context: MiddlewareContext[mt.CallToolRequestParams]) -> ToolResult:
    """A call_next the gate must never reach."""
    raise AssertionError("the gate let the call through")


async def raise_operational_error(session: AsyncSession) -> set[str]:
    """Stand in for the disabled-plugins lookup when the database is unreachable."""
    raise OperationalError("SELECT 1", {}, Exception("connection lost"))


async def seed_plugin(session: AsyncSession, name: str, enabled: bool) -> Plugin:
    plugin = Plugin(name=name, enabled=enabled)
    session.add(plugin)
    await session.commit()
    await session.refresh(plugin)
    return plugin


def gated_server(*middleware: Any) -> FastMCP:
    """A server carrying the gate, plus one plugin tool and one tool owned by no plugin."""
    server = FastMCP(name="test-plugin-gate")
    for extra in middleware:
        server.add_middleware(extra)
    server.add_middleware(PluginToolAccessMiddleware())
    server.tool(name=PLUGIN_TOOL, description="Owned by a plugin", meta={PLUGIN_NAME_META_KEY: "chat"})(
        audited_tool(echo)
    )
    server.tool(name=CORE_TOOL, description="Owned by no plugin")(audited_tool(echo))
    return server


class TestToolPluginResolution:
    """Which plugin owns a registered tool."""

    async def test_a_registered_plugin_tool_carries_its_plugin_name(self) -> None:
        """register_plugin_tools stamps the contributing plugin onto the tool, which is
        the only record of ownership the gate has at call time."""
        try:
            _register_tool(Tool(echo), "slack", {})
            tool = await mcp.get_tool("echo")
            assert tool is not None
            assert get_tool_plugin_name(tool) == "slack"
        finally:
            mcp.local_provider.remove_tool("echo")

    async def test_a_tool_registered_directly_on_the_server_has_no_plugin(self) -> None:
        tool = await mcp.get_tool("get_course_generation_prompt_tool")
        assert tool is not None
        assert get_tool_plugin_name(tool) is None


class TestToolCallGate:
    """Whether a tools/call is allowed through."""

    async def test_rejects_a_tool_whose_plugin_is_disabled_system_wide(self, session: AsyncSession) -> None:
        await seed_plugin(session, "chat", enabled=False)

        async with Client(gated_server()) as client:
            with pytest.raises(ToolError) as rejection:
                await client.call_tool(PLUGIN_TOOL, {"value": "x"})

        assert "chat" in str(rejection.value)

    async def test_runs_a_tool_whose_plugin_is_enabled(self, session: AsyncSession) -> None:
        await seed_plugin(session, "chat", enabled=True)

        async with Client(gated_server()) as client:
            result = await client.call_tool(PLUGIN_TOOL, {"value": "ran"})

        assert result.data == "ran"

    async def test_runs_a_tool_whose_plugin_has_no_database_row(self, session: AsyncSession) -> None:
        """A plugin the registry has never seen is not a disabled plugin. Defaulting the
        other way would make every tool unreachable until the row exists."""
        async with Client(gated_server()) as client:
            result = await client.call_tool(PLUGIN_TOOL, {"value": "ran"})

        assert result.data == "ran"

    async def test_leaves_a_tool_that_belongs_to_no_plugin_alone(self, session: AsyncSession) -> None:
        await seed_plugin(session, "chat", enabled=False)

        async with Client(gated_server()) as client:
            result = await client.call_tool(CORE_TOOL, {"value": "ran"})

        assert result.data == "ran"

    async def test_reads_the_flag_at_call_time_not_at_registration_time(self, session: AsyncSession) -> None:
        """The test that fails if the check ever moves into register_plugin_tools: the
        plugin is disabled after the server is built, with no re-registration."""
        plugin = await seed_plugin(session, "chat", enabled=True)
        server = gated_server()

        async with Client(server) as client:
            assert (await client.call_tool(PLUGIN_TOOL, {"value": "ran"})).data == "ran"

        plugin.enabled = False
        session.add(plugin)
        await session.commit()

        async with Client(server) as client:
            with pytest.raises(ToolError):
                await client.call_tool(PLUGIN_TOOL, {"value": "x"})

    async def test_a_database_error_blocks_the_call(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The gate fails closed: a lookup that could not complete is not permission to run."""
        monkeypatch.setattr("sparkth.mcp.access.system_disabled_plugin_names", raise_operational_error)

        async with Client(gated_server()) as client:
            with pytest.raises(ToolError):
                await client.call_tool(PLUGIN_TOOL, {"value": "x"})

    async def test_a_call_carrying_no_server_context_is_blocked(self) -> None:
        """Without the FastMCP context there is no server to resolve the tool's plugin
        from, so the gate cannot answer its own question. Every path FastMCP serves today
        populates it; the guard exists because the alternative to refusing is waving an
        unresolvable call straight through, which is what an inert gate looks like."""
        context = cast(
            "MiddlewareContext[mt.CallToolRequestParams]",
            SimpleNamespace(
                fastmcp_context=None,
                message=mt.CallToolRequestParams(name=PLUGIN_TOOL, arguments={}),
            ),
        )

        with pytest.raises(ToolError):
            await PluginToolAccessMiddleware().on_call_tool(context, unreachable_call_next)


class TestToolListingFilter:
    """What a tools/list advertises."""

    async def test_hides_tools_whose_plugin_is_disabled(self, session: AsyncSession) -> None:
        await seed_plugin(session, "chat", enabled=False)

        async with Client(gated_server()) as client:
            listed = [tool.name for tool in await client.list_tools()]

        assert PLUGIN_TOOL not in listed
        assert CORE_TOOL in listed

    async def test_keeps_tools_whose_plugin_is_enabled(self, session: AsyncSession) -> None:
        await seed_plugin(session, "chat", enabled=True)

        async with Client(gated_server()) as client:
            listed = [tool.name for tool in await client.list_tools()]

        assert PLUGIN_TOOL in listed

    async def test_a_database_error_leaves_the_listing_unfiltered(
        self, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Deliberately the opposite of the call gate. The lifespan lists tools to log how
        many are registered, so a raising filter would take startup down with it — and the
        listing is discoverability, not the boundary. The call is still refused."""
        monkeypatch.setattr("sparkth.mcp.access.system_disabled_plugin_names", raise_operational_error)

        async with Client(gated_server()) as client:
            listed = [tool.name for tool in await client.list_tools()]

        assert PLUGIN_TOOL in listed


class TestServerWiring:
    """The gate as the shared server actually carries it."""

    def test_the_server_carries_the_gate(self) -> None:
        assert any(isinstance(middleware, PluginToolAccessMiddleware) for middleware in mcp.middleware)

    def test_the_gate_is_registered_inside_the_audit_backstop(self) -> None:
        """FastMCP runs the first-added middleware outermost, so the audit backstop must be
        added first for it to observe the calls the gate rejects."""
        types = [type(middleware) for middleware in mcp.middleware]
        assert types.index(ToolCallAuditMiddleware) < types.index(PluginToolAccessMiddleware)

    async def test_a_rejected_call_is_still_audited(
        self, session: AsyncSession, audit_events: AuditEventsFetcher
    ) -> None:
        """A blocked tool call is exactly the kind of event the audit log exists for."""
        await seed_plugin(session, "chat", enabled=False)

        async with Client(gated_server(ToolCallAuditMiddleware())) as client:
            with pytest.raises(ToolError):
                await client.call_tool(PLUGIN_TOOL, {"value": "x"})

        rows = await audit_events()
        assert [(row.category, row.action) for row in rows] == [("tool", "failed")]
        assert rows[0].tool_name == PLUGIN_TOOL
