from datetime import datetime

from sparkth.lib.chat.hooks import ChatResponsibility
from sparkth.plugins.chat.constants import (
    DEFAULT_RESPONSIBILITY,
    MESSAGE_SCOPE_CLASSIFIER_SYSTEM_PROMPT,
    NO_RESPONSIBILITY,
    REFUSAL_MESSAGE,
)


def render_system_prompt(responsibility: ChatResponsibility) -> str:
    """Render the system prompt of the job a conversation does.

    No language is injected. Each job's template tells the model to write in the language of
    the user's most recent message and to switch when the user does, so the output language
    is inferred from the conversation, not resolved from stored state.

    The date is the only substitution that varies per request. The refusal sentence is the
    English source constant, which the model is told to send in the conversation's language.
    """
    return responsibility.system_prompt.format(
        current_datetime=datetime.now(),
        refusal_message=REFUSAL_MESSAGE,
    )


def render_scope_classifier_prompt(jobs: dict[str, ChatResponsibility]) -> str:
    """Render the scope classifier's system prompt, listing ``jobs``.

    Each job appears under its name, which is the value the classifier must answer with, and
    its scope, which is what the classifier judges against. Rendered per request from the
    enabled jobs, so nothing depends on which plugin was imported first.
    """
    listed = "\n\n".join(f'JOB "{name}":\n{responsibility.scope}' for name, responsibility in jobs.items())
    return MESSAGE_SCOPE_CLASSIFIER_SYSTEM_PROMPT.format(
        responsibilities=listed, default_job=DEFAULT_RESPONSIBILITY, no_job=NO_RESPONSIBILITY
    )
