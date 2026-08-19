"""Plugin access gate for the FastMCP server.

Switching a plugin off must switch off everything it contributes, and its MCP
tools are one of those things. This middleware is where that is enforced for
``/ai/mcp``: it refuses ``tools/call`` for a tool whose plugin an administrator
has disabled system-wide, and drops those tools from ``tools/list`` so a client
is not offered something it cannot use.

The owning plugin is read from the tool itself — ``register_plugin_tools``
stamps the contributing plugin's name into the tool's ``meta`` at registration
(:data:`PLUGIN_NAME_META_KEY`), the same way ``register_router`` stamps it onto
plugin endpoints for the HTTP gate. A tool registered directly on the server
belongs to no plugin and is never gated.

The flag is read on every call rather than at registration: tools are registered
once during the lifespan, while ``Plugin.enabled`` flips at runtime. Filtering at
registration would leave a plugin disabled afterwards fully callable, and one
re-enabled afterwards dark until the next restart.

Enforcement is system-wide only. A per-user preference needs a user, and the MCP
surface carries no authenticated caller to check one against.
"""

from collections.abc import Sequence

import mcp.types as mt
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools import Tool, ToolResult
from sqlalchemy.exc import DatabaseError, OperationalError

from sparkth.core.plugins.service import system_disabled_plugin_names
from sparkth.lib.db import session_scope
from sparkth.lib.log import get_logger

logger = get_logger(__name__)

# The key under which a tool's ``meta`` carries the name of the plugin that
# contributed it. Written by ``register_plugin_tools``, read back here.
PLUGIN_NAME_META_KEY = "plugin_name"


def get_tool_plugin_name(tool: Tool) -> str | None:
    """Name of the plugin that contributed ``tool``, or None when no plugin did.

    Args:
        tool: A tool registered on the FastMCP server.

    Returns:
        The plugin name stamped at registration, or None for a tool registered
        directly on the server rather than through the ``MCP_TOOLS`` hook.
    """
    plugin_name = (tool.meta or {}).get(PLUGIN_NAME_META_KEY)
    if not isinstance(plugin_name, str) or not plugin_name:
        return None
    return plugin_name


async def disabled_plugins() -> set[str]:
    """The system-disabled plugin names, in a session of this middleware's own.

    The gate runs outside the FastAPI request cycle, so there is no injected
    session to borrow.

    Returns:
        The set of disabled plugin names.

    Raises:
        DatabaseError: If the registry could not be read.
        OperationalError: If the database could not be reached.
    """
    async with session_scope() as session:
        return await system_disabled_plugin_names(session)


class PluginToolAccessMiddleware(Middleware):
    """Refuse and hide the MCP tools of plugins that are switched off."""

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        """Reject the call when the tool's plugin is disabled.

        Fails closed: a lookup that could not complete is not permission to run, so a
        database failure refuses the call rather than letting it through unchecked.

        A tool owned by no plugin — and an unknown tool name, which resolves to no tool
        at all — reaches the handler without the gate touching the database.
        """
        fastmcp_context = context.fastmcp_context
        if fastmcp_context is None:
            # Every path FastMCP serves today populates this. The guard is here because
            # without it there is no server to resolve ownership from, and a gate that
            # cannot answer its own question must refuse rather than wave the call
            # through — an inert gate is the failure mode worth being loud about.
            logger.error(f"Refused tool '{context.message.name}': no server context to resolve its plugin from")
            raise ToolError(f"Tool '{context.message.name}' is unavailable.")

        plugin_name = await self._owning_plugin(fastmcp_context.fastmcp, context.message.name)
        if plugin_name is None:
            return await call_next(context)

        try:
            disabled = await disabled_plugins()
        except (DatabaseError, OperationalError) as e:
            logger.error(f"Database error checking plugin '{plugin_name}' for tool '{context.message.name}': {e}")
            raise ToolError(f"Tool '{context.message.name}' is unavailable.") from e

        if plugin_name in disabled:
            logger.warning(f"Refused tool '{context.message.name}': its plugin '{plugin_name}' is disabled system-wide")
            raise ToolError(f"Tool '{context.message.name}' is unavailable: the '{plugin_name}' plugin is disabled.")

        return await call_next(context)

    async def on_list_tools(
        self,
        context: MiddlewareContext[mt.ListToolsRequest],
        call_next: CallNext[mt.ListToolsRequest, Sequence[Tool]],
    ) -> Sequence[Tool]:
        """Drop the tools of disabled plugins from the advertised listing.

        Deliberately the opposite of :meth:`on_call_tool` on failure: a database error
        here is logged and the listing returned unfiltered. The lifespan lists the tools
        to log how many are registered, so a raising filter would take startup down with
        it, and the listing is discoverability rather than the boundary — a tool that
        slips into the listing is still refused when it is called.
        """
        tools = await call_next(context)

        try:
            disabled = await disabled_plugins()
        except (DatabaseError, OperationalError) as e:
            logger.error(f"Database error filtering the MCP tool listing; advertising every tool: {e}")
            return tools

        return [tool for tool in tools if get_tool_plugin_name(tool) not in disabled]

    @staticmethod
    async def _owning_plugin(server: FastMCP, tool_name: str) -> str | None:
        """Name of the plugin owning ``tool_name``, or None when no plugin owns it.

        An unknown tool name resolves to no tool and so to no plugin; the protocol layer
        below the gate is what rejects it.

        Args:
            server: The FastMCP server the tool is registered on.
            tool_name: The tool the call names.

        Returns:
            The owning plugin's name, or None for a tool registered directly on the server.
        """
        tool = await server.get_tool(tool_name)
        if tool is None:
            return None

        return get_tool_plugin_name(tool)
