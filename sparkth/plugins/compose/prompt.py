from datetime import datetime

from sparkth.lib.compose.hooks import Agent
from sparkth.plugins.compose.constants import (
    MESSAGE_SCOPE_CLASSIFIER_SYSTEM_PROMPT,
    REFUSAL_MESSAGE,
    SYSTEM_PROMPT_SKELETON,
)


def render_system_prompt(agents: list[Agent]) -> str:
    """Render the Compose system prompt: Compose's skeleton with each agent's prompt under its title.

    The skeleton holds every rule the agents share: the date, the assistant's identity, the
    output language, the response boundaries and the offering-choices format. It also carries
    Compose's own LMS operations. Each prompt is inserted as a value, never formatted, so a brace
    in it reaches the model as written.

    No language is injected. The skeleton tells the model to write in the language of the
    user's most recent message and to switch when the user does. The date is the only
    substitution that varies per request. The refusal sentence is the English source constant,
    which the model is told to send in the conversation's language.
    """
    capabilities = "\n\n".join(f"## {agent.title}\n{agent.prompt}" for agent in agents)
    return SYSTEM_PROMPT_SKELETON.format(
        current_datetime=datetime.now(),
        refusal_message=REFUSAL_MESSAGE,
        capabilities=capabilities,
    )


def render_scope_classifier_prompt(agents: list[Agent]) -> str:
    """Render the scope classifier's system prompt, listing each of ``agents`` by its title and
    its description, which is what the classifier judges a message against, after Compose's own
    LMS operations.

    Rendered per request from the enabled agents, so nothing depends on which plugin was
    imported first.
    """
    listed = "\n\n".join(f'CAPABILITY "{agent.title}":\n{agent.description}' for agent in agents)
    return MESSAGE_SCOPE_CLASSIFIER_SYSTEM_PROMPT.format(capabilities=listed)
