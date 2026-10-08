"""Hook through which a plugin gives the chat assistant a job it can do.

A *responsibility* is one job a chat conversation can be for, such as designing a course. Every
conversation does exactly one. The chat plugin asks a classifier which enabled job a new
conversation's first message belongs to, stores the answer on the conversation, and from then on
builds each turn from that job: its system prompt and the MCP tool categories it binds.

The hook lives in ``sparkth.lib`` so a plugin can register a job without importing chat. It is
keyed by plugin, so a job is offered only while its plugin is switched on. A plugin registers
one job from its ``__init__``::

    CHAT_RESPONSIBILITIES.add_item(self, ChatResponsibility("my-job", SCOPE, PROMPT, frozenset({"my-tools"})))
"""

from dataclasses import dataclass

from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.plugins.service import system_disabled_plugin_names
from sparkth.lib.chat.constants import CHAT_RESPONSIBILITY_NAME_MAX_LENGTH
from sparkth.lib.hooks import PluginHook
from sparkth.lib.log import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ChatResponsibility:
    """One job a chat conversation can be for.

    ``name`` is a slug, stored on every conversation doing this job, so it must never change
    once shipped. It is at most ``CHAT_RESPONSIBILITY_NAME_MAX_LENGTH`` characters, the size of
    that stored column, and a longer one raises ``ValueError``. ``scope`` is the text the
    classifier reads to decide whether a message belongs to this job. ``system_prompt`` is a
    ``str.format`` template that receives ``current_datetime`` and ``refusal_message``, so any
    other literal brace is doubled.
    ``tool_categories`` names the ``MCP_TOOLS`` categories this job claims.

    A frozen dataclass, so the copies registered by repeated plugin constructions compare equal.
    """

    name: str
    scope: str
    system_prompt: str
    tool_categories: frozenset[str]

    def __post_init__(self) -> None:
        if len(self.name) > CHAT_RESPONSIBILITY_NAME_MAX_LENGTH:
            raise ValueError(
                f"Chat responsibility name {self.name!r} exceeds {CHAT_RESPONSIBILITY_NAME_MAX_LENGTH} characters"
            )


# One chat responsibility per plugin, consumed by the chat plugin. Keyed by plugin instance,
# so constructing a plugin again re-registers it harmlessly.
CHAT_RESPONSIBILITIES: PluginHook[ChatResponsibility] = PluginHook()


async def enabled_responsibilities(session: AsyncSession) -> dict[str, ChatResponsibility]:
    """Return the jobs chat offers right now, by name.

    Leaves out the job of every plugin an administrator switched off system-wide. Read per
    request rather than cached, because ``Plugin.enabled`` flips at runtime.

    Equal copies from repeated constructions of one plugin fold into one entry. When two
    different plugins claim one name, the first in plugin-name order is kept and the other is
    logged and ignored, because conversations store the name and the two would route each
    other's conversations.
    """
    disabled = await system_disabled_plugin_names(session)
    jobs: dict[str, ChatResponsibility] = {}
    for plugin, responsibility in CHAT_RESPONSIBILITIES.iter_items():
        if plugin.name in disabled:
            continue
        kept = jobs.setdefault(responsibility.name, responsibility)
        if kept != responsibility:
            logger.error(
                "Plugin '%s' registers chat responsibility '%s', already claimed by another plugin; ignoring it",
                plugin.name,
                responsibility.name,
            )
    return jobs
