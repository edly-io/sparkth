"""Hook through which a plugin gives the chat assistant a job it can do.

A *responsibility* is one job the chat assistant does, such as designing a course. Chat reads
the enabled jobs on every request. A classifier judges each message against every enabled job's
scope and refuses one that fits none. The turn's system prompt is chat's skeleton with every
enabled job's prompt section under its title, and the turn gets every tool the request asks for.

The hook lives in ``sparkth.lib`` so a plugin can register a job without importing chat. It is
keyed by plugin, so a job is offered only while its plugin is switched on. A plugin registers
one job from its ``__init__``::

    CHAT_RESPONSIBILITIES.add_item(
        self, ChatResponsibility("my-job", LABEL, TITLE, SCOPE, PROMPT, frozenset({"my-tools"}))
    )
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
    """One job the chat assistant does.

    ``name`` is a slug that identifies the job. It is at most
    ``CHAT_RESPONSIBILITY_NAME_MAX_LENGTH`` characters, and a longer one raises
    ``ValueError``. ``label`` is the job's name as authors would see it, marked with
    ``gettext_noop``. ``title`` is the heading
    the job's ``prompt`` is rendered under in the chat system prompt. ``scope`` is the text the
    classifier reads to decide whether a message belongs to this job. ``prompt`` is the job's
    section of the system prompt: plain text inserted as written, never formatted, so a brace
    needs no escaping. It holds only what is specific to the job, because chat's skeleton carries
    the date, identity, output language, refusal and offering-choices rules. ``tool_categories``
    is not read by chat: every turn gets every tool the request asks for.

    A frozen dataclass, so the copies registered by repeated plugin constructions compare equal.
    """

    name: str
    label: str
    title: str
    scope: str
    prompt: str
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
    logged and ignored, because both would be offered under one name.
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
