"""Hook through which a plugin gives Compose an agent.

An *agent* does one kind of work for Compose, such as designing a course.

The hook lives in ``sparkth.lib`` so a plugin can contribute an agent without importing compose.
It is keyed by plugin, so an agent is offered only while its plugin is switched on for the user,
by both switches. A plugin registers one agent from its ``__init__``, after its ``MCP_TOOLS``::

    register_agent(self, Agent(NAME, TITLE, DESCRIPTION, PROMPT, tools=(...)))
"""

from dataclasses import dataclass, field

from langchain_core.tools import BaseTool

from sparkth.lib.compose.constants import AGENT_NAME_PATTERN, RESERVED_AGENT_NAMES
from sparkth.lib.compose.exceptions import (
    DuplicateAgentName,
    DuplicateAgentTool,
    InvalidAgentName,
    ReservedAgentName,
    UnknownAgentTool,
)
from sparkth.lib.hooks import PluginHook
from sparkth.lib.log import get_logger
from sparkth.lib.mcp.hooks import MCP_TOOLS
from sparkth.lib.plugins import SparkthPlugin

logger = get_logger(__name__)


@dataclass(frozen=True)
class Agent:
    """One kind of work Compose hands to a plugin.

    ``name`` identifies the agent (``^[a-z][a-z0-9_]*$``), ``title`` heads its section of the system
    prompt, ``description`` is what Compose reads to decide a message is the agent's, ``prompt`` is
    inserted as written, ``tools`` names the plugin's own MCP tools, and ``langchain_tools`` are
    tools only the agent runs, which no MCP client sees. A LangChain tool runs in every turn the
    agent answers, whatever tools the request enables.

    A frozen dataclass, so the copies registered by repeated plugin constructions compare equal.
    LangChain tools take no part in the comparison, so a plugin may build them on each construction.
    """

    name: str
    title: str
    description: str
    prompt: str
    tools: tuple[str, ...] = ()
    langchain_tools: tuple[BaseTool, ...] = field(default=(), compare=False)


# One agent per plugin, consumed by the compose plugin. Keyed by plugin instance, so constructing
# a plugin again re-registers it harmlessly. Register through register_agent, which validates.
COMPOSE_AGENTS: PluginHook[Agent] = PluginHook()


def register_agent(plugin: SparkthPlugin, agent: Agent) -> None:
    """Register ``plugin``'s ``agent`` on ``COMPOSE_AGENTS``.

    Call this from a plugin's ``__init__``, after registering its ``MCP_TOOLS``. An equal agent
    arriving again from another construction of the same plugin is accepted.

    Raises :class:`~sparkth.lib.compose.exceptions.InvalidAgentName`,
    :class:`~sparkth.lib.compose.exceptions.ReservedAgentName`,
    :class:`~sparkth.lib.compose.exceptions.DuplicateAgentName` when another agent, another
    plugin or a registered MCP tool holds the name,
    :class:`~sparkth.lib.compose.exceptions.UnknownAgentTool` for a tool name the plugin doesn't own,
    or :class:`~sparkth.lib.compose.exceptions.DuplicateAgentTool` when two of the agent's tools
    share a name or a LangChain tool takes a registered MCP tool's name.
    """
    if not AGENT_NAME_PATTERN.fullmatch(agent.name):
        logger.error("Agent name '%s' is not a valid tool name", agent.name)
        raise InvalidAgentName(agent.name)
    if agent.name in RESERVED_AGENT_NAMES:
        logger.error("Agent name '%s' is reserved for Compose", agent.name)
        raise ReservedAgentName(agent.name)
    if any(
        registered.name == agent.name and (registered != agent or owner.name != plugin.name)
        for owner, registered in COMPOSE_AGENTS.iter_items()
    ):
        logger.error("Agent '%s' collides with an agent already registered", agent.name)
        raise DuplicateAgentName(agent.name)
    if any(tool.name == agent.name for _owner, tool in MCP_TOOLS.iter_items()):
        logger.error("Agent name '%s' is already an MCP tool name", agent.name)
        raise DuplicateAgentName(agent.name)
    owned = {tool.name for owner, tool in MCP_TOOLS.iter_items() if owner is plugin}
    for tool_name in agent.tools:
        if tool_name not in owned:
            logger.error(
                "Agent '%s' names tool '%s', which plugin '%s' doesn't own", agent.name, tool_name, plugin.name
            )
            raise UnknownAgentTool(agent.name, tool_name)
    langchain_names = [tool.name for tool in agent.langchain_tools]
    names = [*agent.tools, *langchain_names]
    mcp_names = {tool.name for _owner, tool in MCP_TOOLS.iter_items()}
    for tool_name in names:
        if names.count(tool_name) > 1 or (tool_name in langchain_names and tool_name in mcp_names):
            logger.error("Agent '%s' has more than one tool named '%s'", agent.name, tool_name)
            raise DuplicateAgentTool(agent.name, tool_name)
    COMPOSE_AGENTS.add_item(plugin, agent)


def enabled_agents(disabled_plugins: set[str]) -> list[Agent]:
    """Return the agents Compose offers, in plugin-name order.

    Leaves out the agent of every plugin named in ``disabled_plugins``, the plugins switched off
    for the requesting user by either switch. Equal copies from repeated constructions of one
    plugin fold into one.
    """
    offered = (agent for plugin, agent in COMPOSE_AGENTS.iter_items() if plugin.name not in disabled_plugins)
    return list(dict.fromkeys(offered))
