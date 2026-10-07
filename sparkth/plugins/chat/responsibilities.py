"""Which job a chat conversation does.

A conversation does exactly one :class:`~sparkth.lib.chat.hooks.ChatResponsibility`, stored by
name on its row. This module turns that name into the job. All of it is pure, so the completion
route only calls it.
"""

from sparkth.lib.chat.hooks import ChatResponsibility
from sparkth.lib.log import get_logger
from sparkth.plugins.chat.constants import (
    COURSE_DESIGN_SCOPE,
    COURSE_DESIGN_SYSTEM_PROMPT,
    DEFAULT_RESPONSIBILITY,
)
from sparkth.plugins.chat.models import Conversation

logger = get_logger(__name__)

# Chat's own job. It claims no tool categories.
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
