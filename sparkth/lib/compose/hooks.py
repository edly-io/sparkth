"""Hook through which a plugin gives the Compose assistant a capability.

A *capability* is one kind of work the Compose assistant does, such as designing a course. On every
request Compose reads the capabilities of the plugins that are switched on for the requesting
user. Its scope classifier refuses a message that belongs to none of their scopes, and the turn's
system prompt is Compose's own skeleton with every capability's prompt section under its title.
Every turn gets the tools the request asks for, except those of plugins switched off for the user.

The hook lives in ``sparkth.lib`` so a plugin can contribute a capability without importing compose.
It is keyed by plugin, so a capability is offered only while its plugin is switched on for the
user, by both switches. A plugin registers one capability from its ``__init__``::

    register_chat_capability(self, ChatCapability(TITLE, SCOPE, PROMPT))
"""

from dataclasses import dataclass

from sparkth.lib.compose.exceptions import DuplicateChatCapabilityError
from sparkth.lib.hooks import PluginHook
from sparkth.lib.log import get_logger
from sparkth.lib.plugins import SparkthPlugin

logger = get_logger(__name__)


@dataclass(frozen=True)
class ChatCapability:
    """One kind of work the Compose assistant does for a plugin.

    ``title`` is the heading the capability is listed under, in Compose's system prompt and in the
    scope classifier's, so it is unique among capabilities. ``scope`` is the text the classifier
    reads to decide whether a message belongs to the capability. ``prompt`` is the capability's
    section of the system prompt: plain text inserted as written, never formatted, holding only
    what is specific to the capability. Compose's skeleton carries the date, identity, output
    language, refusal and offering-choices rules.

    A frozen dataclass, so the copies registered by repeated plugin constructions compare equal.
    """

    title: str
    scope: str
    prompt: str


# One chat capability per plugin, consumed by the compose plugin. Keyed by plugin instance,
# so constructing a plugin again re-registers it harmlessly. Register through
# register_chat_capability, which refuses a clashing title.
CHAT_CAPABILITIES: PluginHook[ChatCapability] = PluginHook()


def register_chat_capability(plugin: SparkthPlugin, capability: ChatCapability) -> None:
    """Register ``plugin``'s ``capability`` on ``CHAT_CAPABILITIES``.

    Call this from a plugin's ``__init__``. A plugin is constructed more than once in one process,
    by the loader and by its own tests, so an equal capability arriving again is accepted and
    :func:`enabled_capabilities` folds the copies into one. Only a *different* capability claiming
    a registered title raises :class:`~sparkth.lib.compose.exceptions.DuplicateChatCapabilityError`.
    """
    if any(
        registered.title == capability.title and registered != capability
        for _owner, registered in CHAT_CAPABILITIES.iter_items()
    ):
        logger.error("Chat capability '%s' collides with a different capability already registered", capability.title)
        raise DuplicateChatCapabilityError(capability.title)
    CHAT_CAPABILITIES.add_item(plugin, capability)


def enabled_capabilities(disabled_plugins: set[str]) -> list[ChatCapability]:
    """Return the capabilities Compose offers, in plugin-name order.

    Leaves out the capability of every plugin named in ``disabled_plugins``, the plugins switched
    off for the requesting user by either switch. Equal copies from repeated constructions of one
    plugin fold into one.
    """
    offered = (
        capability for plugin, capability in CHAT_CAPABILITIES.iter_items() if plugin.name not in disabled_plugins
    )
    return list(dict.fromkeys(offered))
