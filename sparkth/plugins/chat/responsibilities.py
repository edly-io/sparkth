"""Which job a chat conversation does, and which tools that job binds.

A conversation does exactly one :class:`~sparkth.lib.chat.hooks.ChatResponsibility`, stored by
name on its row. This module turns that name into the job and decides which MCP tool categories
the job binds. All of it is pure, so the completion route only calls it.
"""

from sparkth.lib.chat.hooks import CHAT_RESPONSIBILITIES, ChatResponsibility
from sparkth.lib.log import get_logger
from sparkth.plugins.chat.constants import (
    COURSE_DESIGN_SCOPE,
    COURSE_DESIGN_SYSTEM_PROMPT,
    DEFAULT_RESPONSIBILITY,
)
from sparkth.plugins.chat.models import Conversation

logger = get_logger(__name__)

# Chat's own job. It claims no tool categories, so it binds every category no other job claims.
COURSE_DESIGN = ChatResponsibility(
    DEFAULT_RESPONSIBILITY, COURSE_DESIGN_SCOPE, COURSE_DESIGN_SYSTEM_PROMPT, frozenset()
)


def stored_responsibility(conversation: Conversation, jobs: dict[str, ChatResponsibility]) -> ChatResponsibility:
    """Return the job ``conversation`` does, from this request's enabled ``jobs``.

    A NULL job reads as course design. A stored job that is not enabled, because its plugin is
    switched off or removed, also falls back to course design. That keeps the conversation
    usable, and it is logged.
    """
    name = conversation.responsibility or DEFAULT_RESPONSIBILITY
    responsibility = jobs.get(name)
    if responsibility is None:
        logger.warning(
            "Conversation %s names responsibility %r, which is not enabled; using %s",
            conversation.uuid,
            name,
            DEFAULT_RESPONSIBILITY,
        )
        return COURSE_DESIGN
    return responsibility


def binds_category(responsibility: ChatResponsibility, category: str) -> bool:
    """Whether a conversation doing ``responsibility`` is given tools of MCP ``category``.

    A job with categories binds exactly those. A job with none, such as course design, binds
    every category no registered job claims, including uncategorised tools. Claims of disabled
    plugins' jobs count too, so a switched-off job's tools never fall through to course design.
    """
    if responsibility.tool_categories:
        return category in responsibility.tool_categories
    return all(category not in other.tool_categories for _plugin, other in CHAT_RESPONSIBILITIES.iter_items())
