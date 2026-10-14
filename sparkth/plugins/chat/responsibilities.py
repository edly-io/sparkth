"""Which job a chat conversation does, and what that job decides about each turn.

A conversation does exactly one :class:`~sparkth.lib.chat.hooks.ChatResponsibility`, stored by
name on its row. This module turns that name into the job and decides whether a turn's classified
job lets it proceed.
"""

from sparkth.lib.chat.hooks import ChatResponsibility, registered_responsibility
from sparkth.lib.i18n import _, gettext
from sparkth.plugins.chat.constants import (
    COURSE_DESIGN_LABEL,
    COURSE_DESIGN_SCOPE,
    COURSE_DESIGN_SYSTEM_PROMPT,
    COURSE_DESIGN_TITLE,
    DEFAULT_RESPONSIBILITY,
    REDIRECT_MESSAGE,
    REFUSAL_MESSAGE,
)
from sparkth.plugins.chat.exceptions import ResponsibilityNotEnabled
from sparkth.plugins.chat.models import Conversation

# Chat's own job. It claims no tool categories, so it binds every category no other job claims.
COURSE_DESIGN = ChatResponsibility(
    DEFAULT_RESPONSIBILITY,
    COURSE_DESIGN_LABEL,
    COURSE_DESIGN_TITLE,
    COURSE_DESIGN_SCOPE,
    COURSE_DESIGN_SYSTEM_PROMPT,
    frozenset(),
)


def stored_responsibility(conversation: Conversation, jobs: dict[str, ChatResponsibility]) -> ChatResponsibility:
    """Return the job ``conversation`` does, from this request's enabled ``jobs``.

    A NULL job reads as course design. A stored job that is not enabled, because its plugin is
    switched off or removed, raises :class:`ResponsibilityNotEnabled` naming the job, so the
    author learns why the conversation cannot continue. A removed plugin's job has no label left,
    so it is named by its stored name.
    """
    name = conversation.responsibility or DEFAULT_RESPONSIBILITY
    responsibility = jobs.get(name)
    if responsibility is None:
        registered = registered_responsibility(name)
        label = gettext(registered.label) if registered else name
        raise ResponsibilityNotEnabled(
            _(
                "This conversation is for {job}, and the plugin that provides it is turned off, "
                "so nothing more can be done here."
            ).format(job=label)
        )
    return responsibility


def refusal_or_redirect(judged: str | None, stored: str) -> str | None:
    """Return the fixed reply that ends a later turn in place of the model, or ``None`` to proceed.

    ``judged`` is the classifier's job for the turn: ``None`` for no job at all, which is
    refused. A different job is redirected to a new conversation, because a conversation never
    changes job.
    """
    if judged is None:
        return REFUSAL_MESSAGE
    if judged != stored:
        return REDIRECT_MESSAGE
    return None
