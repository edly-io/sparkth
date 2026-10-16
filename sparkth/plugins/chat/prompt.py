from datetime import datetime

from sparkth.lib.chat.hooks import ChatResponsibility
from sparkth.plugins.chat.constants import (
    DEFAULT_RESPONSIBILITY,
    MESSAGE_SCOPE_CLASSIFIER_SYSTEM_PROMPT,
    NO_RESPONSIBILITY,
    REFUSAL_MESSAGE,
    SYSTEM_PROMPT_SKELETON,
)


def render_system_prompt(sections: list[ChatResponsibility]) -> str:
    """Render the chat system prompt: chat's skeleton with each of ``sections`` under its title.

    The skeleton holds every rule the sections share: the date, the assistant's identity, the
    output language, the response boundaries and the offering-choices format. Each section is
    inserted as a value, never formatted, so a brace in it reaches the model as written.

    No language is injected. The skeleton tells the model to write in the language of the
    user's most recent message and to switch when the user does. The date is the only
    substitution that varies per request. The refusal sentence is the English source constant,
    which the model is told to send in the conversation's language.
    """
    capabilities = "\n\n".join(f"## {section.title}\n{section.prompt}" for section in sections)
    return SYSTEM_PROMPT_SKELETON.format(
        current_datetime=datetime.now(),
        refusal_message=REFUSAL_MESSAGE,
        capabilities=capabilities,
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
