"""Hook through which a plugin gives Compose an agent.

An *agent* does one kind of work for Compose, such as designing a course. On every request
Compose reads the agents of the plugins that are switched on for the requesting user. Its scope
classifier refuses a message that fits none of their descriptions, and the turn's system prompt is
Compose's own skeleton with every agent's prompt under its title. Every turn gets the tools the
request asks for, except those of plugins switched off for the user.

The hook lives in ``sparkth.lib`` so a plugin can contribute an agent without importing compose.
It is keyed by plugin, so an agent is offered only while its plugin is switched on for the user,
by both switches. A plugin registers one agent from its ``__init__``::

    register_agent(self, Agent(TITLE, DESCRIPTION, PROMPT))
"""

from dataclasses import dataclass

from sparkth.lib.compose.exceptions import DuplicateAgentTitle
from sparkth.lib.hooks import PluginHook
from sparkth.lib.log import get_logger
from sparkth.lib.plugins import SparkthPlugin

logger = get_logger(__name__)


@dataclass(frozen=True)
class Agent:
    """One kind of work Compose hands to a plugin.

    A frozen dataclass, so the copies registered by repeated plugin constructions compare equal.
    """

    title: str  # unique heading of the agent's section in the system prompt
    description: str  # what Compose reads to decide a message is the agent's
    prompt: str  # the agent's instructions, inserted as written


# One agent per plugin, consumed by the compose plugin. Keyed by plugin instance, so constructing
# a plugin again re-registers it harmlessly. Register through register_agent, which refuses a
# clashing title.
COMPOSE_AGENTS: PluginHook[Agent] = PluginHook()


def register_agent(plugin: SparkthPlugin, agent: Agent) -> None:
    """Register ``plugin``'s ``agent`` on ``COMPOSE_AGENTS``.

    Call this from a plugin's ``__init__``. An equal agent arriving again from another construction
    of the plugin is accepted. Raises :class:`~sparkth.lib.compose.exceptions.DuplicateAgentTitle`
    when a different agent holds the title.
    """
    if any(
        registered.title == agent.title and registered != agent for _owner, registered in COMPOSE_AGENTS.iter_items()
    ):
        logger.error("Agent '%s' collides with a different agent already registered", agent.title)
        raise DuplicateAgentTitle(agent.title)
    COMPOSE_AGENTS.add_item(plugin, agent)


def enabled_agents(disabled_plugins: set[str]) -> list[Agent]:
    """Return the agents Compose offers, in plugin-name order.

    Leaves out the agent of every plugin named in ``disabled_plugins``, the plugins switched off
    for the requesting user by either switch. Equal copies from repeated constructions of one
    plugin fold into one.
    """
    offered = (agent for plugin, agent in COMPOSE_AGENTS.iter_items() if plugin.name not in disabled_plugins)
    return list(dict.fromkeys(offered))
