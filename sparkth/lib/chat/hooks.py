"""Hook through which a plugin gives the chat assistant a capability.

A *capability* is one kind of work the chat assistant does, such as designing a course. On every
request chat reads the capabilities of the plugins that are switched on. Its scope classifier
refuses a message that belongs to none of their scopes, and the turn's system prompt is chat's
own skeleton with every capability's prompt section under its title. Every turn gets all the
tools the request asks for.

The hook lives in ``sparkth.lib`` so a plugin can contribute a capability without importing chat.
It is keyed by plugin, so a capability is offered only while its plugin is switched on. A plugin
registers one capability from its ``__init__``::

    CHAT_CAPABILITIES.add_item(self, ChatCapability(TITLE, SCOPE, PROMPT))
"""

from dataclasses import dataclass

from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.plugins.service import system_disabled_plugin_names
from sparkth.lib.hooks import PluginHook


@dataclass(frozen=True)
class ChatCapability:
    """One kind of work the chat assistant does for a plugin.

    ``title`` is the heading the capability is listed under, in chat's system prompt and in the
    scope classifier's. ``scope`` is the text the classifier reads to decide whether a message
    belongs to the capability. ``prompt`` is the capability's section of the system prompt: plain
    text inserted as written, never formatted, holding only what is specific to the capability.
    Chat's skeleton carries the date, identity, output language, refusal and offering-choices
    rules.

    A frozen dataclass, so the copies registered by repeated plugin constructions compare equal.
    """

    title: str
    scope: str
    prompt: str


# One chat capability per plugin, consumed by the chat plugin. Keyed by plugin instance,
# so constructing a plugin again re-registers it harmlessly.
CHAT_CAPABILITIES: PluginHook[ChatCapability] = PluginHook()


async def enabled_capabilities(session: AsyncSession) -> list[ChatCapability]:
    """Return the capabilities chat offers right now, in plugin-name order.

    Leaves out the capability of every plugin an administrator switched off system-wide. Read
    per request rather than cached, because ``Plugin.enabled`` flips at runtime. Equal copies
    from repeated constructions of one plugin fold into one.
    """
    disabled = await system_disabled_plugin_names(session)
    offered = (capability for plugin, capability in CHAT_CAPABILITIES.iter_items() if plugin.name not in disabled)
    return list(dict.fromkeys(offered))
