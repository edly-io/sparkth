from datetime import datetime

from sparkth.lib.chat.hooks import ChatResponsibility
from sparkth.plugins.chat.constants import (
    MESSAGE_SCOPE_CLASSIFIER_SYSTEM_PROMPT,
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


def render_scope_classifier_prompt(capabilities: list[ChatResponsibility]) -> str:
    """Render the scope classifier's system prompt, listing each of ``capabilities`` by its title
    and its scope, which is what the classifier judges a message against.

    Rendered per request from the enabled capabilities, so nothing depends on which plugin was
    imported first.
    """
    listed = "\n\n".join(f'CAPABILITY "{capability.title}":\n{capability.scope}' for capability in capabilities)
    return MESSAGE_SCOPE_CLASSIFIER_SYSTEM_PROMPT.format(capabilities=listed)
