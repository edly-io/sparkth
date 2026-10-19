"""Hook through which a plugin gives the chat assistant a capability.

A *capability* is one kind of work the chat assistant does, such as designing a course. On every
request chat reads the capabilities of the plugins that are switched on. Its scope classifier
refuses a message that belongs to none of their scopes, and the turn's system prompt is chat's
own skeleton with every capability's prompt section under its title. Every turn gets all the
tools the request asks for.

The hook lives in ``sparkth.lib`` so a plugin can contribute a capability without importing chat.
It is keyed by plugin, so a capability is offered only while its plugin is switched on. A plugin
registers one capability from its ``__init__``::

    register_chat_capability(self, ChatCapability(TITLE, SCOPE, PROMPT))
"""

from dataclasses import dataclass

from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.plugins.service import disabled_plugin_names
from sparkth.lib.chat.exceptions import DuplicateChatCapabilityError
from sparkth.lib.hooks import PluginHook
from sparkth.lib.log import get_logger
from sparkth.lib.plugins import SparkthPlugin

logger = get_logger(__name__)


@dataclass(frozen=True)
class ChatCapability:
    """One kind of work the chat assistant does for a plugin.

    ``title`` is the heading the capability is listed under, in chat's system prompt and in the
    scope classifier's, so it is unique among capabilities. ``scope`` is the text the classifier
    reads to decide whether a message belongs to the capability. ``prompt`` is the capability's
    section of the system prompt: plain text inserted as written, never formatted, holding only
    what is specific to the capability. Chat's skeleton carries the date, identity, output
    language, refusal and offering-choices rules.

    A frozen dataclass, so the copies registered by repeated plugin constructions compare equal.
    """

    title: str
    scope: str
    prompt: str


# One chat capability per plugin, consumed by the chat plugin. Keyed by plugin instance,
# so constructing a plugin again re-registers it harmlessly. Register through
# register_chat_capability, which refuses a clashing title.
CHAT_CAPABILITIES: PluginHook[ChatCapability] = PluginHook()


def register_chat_capability(plugin: SparkthPlugin, capability: ChatCapability) -> None:
    """Register ``plugin``'s ``capability`` on ``CHAT_CAPABILITIES``.

    Call this from a plugin's ``__init__``. A plugin is constructed more than once in one process,
    by the loader and by its own tests, so an equal capability arriving again is accepted and
    :func:`enabled_capabilities` folds the copies into one. Only a *different* capability claiming
    a registered title raises :class:`~sparkth.lib.chat.exceptions.DuplicateChatCapabilityError`.
    """
    if any(
        registered.title == capability.title and registered != capability
        for _owner, registered in CHAT_CAPABILITIES.iter_items()
    ):
        logger.error("Chat capability '%s' collides with a different capability already registered", capability.title)
        raise DuplicateChatCapabilityError(capability.title)
    CHAT_CAPABILITIES.add_item(plugin, capability)


async def enabled_capabilities(session: AsyncSession) -> list[ChatCapability]:
    """Return the capabilities chat offers right now, in plugin-name order.

    Leaves out the capability of every plugin an administrator switched off system-wide. Read
    per request rather than cached, because ``Plugin.enabled`` flips at runtime. Equal copies
    from repeated constructions of one plugin fold into one.
    """
    disabled = await disabled_plugin_names(None, session)
    offered = (capability for plugin, capability in CHAT_CAPABILITIES.iter_items() if plugin.name not in disabled)
    return list(dict.fromkeys(offered))
