"""Hook through which a plugin gives Compose an agent.

An *agent* does one kind of work for Compose, such as designing a course.

The hook lives in ``sparkth.lib`` so a plugin can contribute an agent without importing compose.
It is keyed by plugin, so an agent is offered only while its plugin is switched on for the user,
by both switches. A plugin registers one agent from its ``__init__``::

    register_agent(self, Agent(NAME, TITLE, DESCRIPTION, PROMPT, tools=(...)))
"""

from dataclasses import dataclass, field

from sparkth.lib.compose.constants import AGENT_NAME_PATTERN, RESERVED_AGENT_NAMES
from sparkth.lib.compose.exceptions import (
    DuplicateAgentName,
    DuplicateAgentTool,
    InvalidAgentName,
    ReservedAgentName,
)
from sparkth.lib.hooks import PluginHook
from sparkth.lib.log import get_logger
from sparkth.lib.mcp.hooks import MCP_TOOLS, Tool
from sparkth.lib.plugins import SparkthPlugin

logger = get_logger(__name__)


@dataclass(frozen=True)
class Agent:
    """One kind of work Compose hands to a plugin.

    ``name`` identifies the agent (``^[a-z][a-z0-9_]*$``), ``title`` heads its section of the system
    prompt, ``description`` is what Compose reads to decide a message is the agent's, ``prompt`` is
    inserted as written, and ``tools`` are the tools the agent runs. A tool given only to the agent
    is seen by no MCP client; one the plugin also gives the MCP server is seen by both.

    A frozen dataclass, so the copies registered by repeated plugin constructions compare equal.
    Tools take no part in the comparison, so a plugin may build them on each construction.
    """

    name: str
    title: str
    description: str
    prompt: str
    tools: tuple[Tool, ...] = field(default=(), compare=False)


# One agent per plugin, consumed by the compose plugin. Keyed by plugin instance, so constructing
# a plugin again re-registers it harmlessly. Register through register_agent, which validates.
COMPOSE_AGENTS: PluginHook[Agent] = PluginHook()


def register_agent(plugin: SparkthPlugin, agent: Agent) -> None:
    """Register ``plugin``'s ``agent`` on ``COMPOSE_AGENTS``.

    Call this from a plugin's ``__init__``. An equal agent arriving again from another construction
    of the same plugin is accepted.

    Raises ``InvalidAgentName``, ``ReservedAgentName``, ``DuplicateAgentName`` when another agent,
    another plugin or a registered MCP tool holds the name, or ``DuplicateAgentTool`` when two of
    the agent's tools share a name.
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
    names = [tool.name for tool in agent.tools]
    for tool_name in names:
        if names.count(tool_name) > 1:
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
