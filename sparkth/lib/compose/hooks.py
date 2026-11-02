"""Hook through which a plugin gives Compose an agent.

An *agent* does one kind of work for Compose, such as designing a course. On every request
Compose reads the agents of the plugins that are switched on for the requesting user. Its scope
classifier refuses a message that fits none of their descriptions, and the turn's system prompt is
Compose's own skeleton with every agent's prompt under its title. Every turn gets the tools the
request asks for, except those of plugins switched off for the user.

The hook lives in ``sparkth.lib`` so a plugin can contribute an agent without importing compose.
It is keyed by plugin, so an agent is offered only while its plugin is switched on for the user,
by both switches. A plugin registers one agent from its ``__init__``, after its ``MCP_TOOLS``::

    register_agent(self, Agent(NAME, TITLE, DESCRIPTION, PROMPT, tools=(...)))
"""

from dataclasses import dataclass

from sparkth.lib.compose.constants import AGENT_NAME_PATTERN, RESERVED_AGENT_NAMES
from sparkth.lib.compose.exceptions import DuplicateAgentName, InvalidAgentName, ReservedAgentName, UnknownAgentTool
from sparkth.lib.hooks import PluginHook
from sparkth.lib.log import get_logger
from sparkth.lib.mcp.hooks import MCP_TOOLS
from sparkth.lib.plugins import SparkthPlugin

logger = get_logger(__name__)


@dataclass(frozen=True)
class Agent:
    """One kind of work Compose hands to a plugin.

    A frozen dataclass, so the copies registered by repeated plugin constructions compare equal.
    """

    name: str  # unique identifier, ``^[a-z][a-z0-9_]*$``
    title: str  # heading of the agent's section in the system prompt
    description: str  # what Compose reads to decide a message is the agent's
    prompt: str  # the agent's instructions, inserted as written
    tools: tuple[str, ...] = ()  # names of the plugin's own MCP tools


# One agent per plugin, consumed by the compose plugin. Keyed by plugin instance, so constructing
# a plugin again re-registers it harmlessly. Register through register_agent, which validates.
COMPOSE_AGENTS: PluginHook[Agent] = PluginHook()


def register_agent(plugin: SparkthPlugin, agent: Agent) -> None:
    """Register ``plugin``'s ``agent`` on ``COMPOSE_AGENTS``.

    Call this from a plugin's ``__init__``, after registering its ``MCP_TOOLS``. An equal agent
    arriving again from another construction of the same plugin is accepted.

    Raises :class:`~sparkth.lib.compose.exceptions.InvalidAgentName`,
    :class:`~sparkth.lib.compose.exceptions.ReservedAgentName`,
    :class:`~sparkth.lib.compose.exceptions.DuplicateAgentName` when another agent or another
    plugin holds the name, or :class:`~sparkth.lib.compose.exceptions.UnknownAgentTool` for a tool the plugin
    doesn't own.
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
    owned = {tool.name for owner, tool in MCP_TOOLS.iter_items() if owner is plugin}
    for tool_name in agent.tools:
        if tool_name not in owned:
            logger.error(
                "Agent '%s' names tool '%s', which plugin '%s' doesn't own", agent.name, tool_name, plugin.name
            )
            raise UnknownAgentTool(agent.name, tool_name)
    COMPOSE_AGENTS.add_item(plugin, agent)


def enabled_agents(disabled_plugins: set[str]) -> list[Agent]:
    """Return the agents Compose offers, in plugin-name order.

    Leaves out the agent of every plugin named in ``disabled_plugins``, the plugins switched off
    for the requesting user by either switch. Equal copies from repeated constructions of one
    plugin fold into one.
    """
    offered = (agent for plugin, agent in COMPOSE_AGENTS.iter_items() if plugin.name not in disabled_plugins)
    return list(dict.fromkeys(offered))
