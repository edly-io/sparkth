from datetime import datetime

from sparkth.lib.compose.hooks import Agent
from sparkth.plugins.compose.constants import (
    REFUSAL_MESSAGE,
    SYSTEM_PROMPT_SKELETON,
)
from sparkth.plugins.compose.enums import OptionsFence


def render_system_prompt(agent: Agent) -> str:
    """Render ``agent``'s system prompt: Compose's skeleton with the agent's prompt under its title.

    The skeleton holds every rule the agents share: the date, the assistant's identity, the
    output language, the response boundaries and the offering-choices format. The agent's prompt is
    inserted as a value, never formatted, so a brace in it reaches the model as written.

    No language is injected. The skeleton tells the model to write in the language of the
    user's most recent message and to switch when the user does. The date is the only
    substitution that varies per request. The refusal sentence is the English source constant,
    which the model is told to send in the conversation's language.
    """
    return SYSTEM_PROMPT_SKELETON.format(
        current_datetime=datetime.now(),
        refusal_message=REFUSAL_MESSAGE,
        work=f"## {agent.title}\n{agent.prompt}",
        options_tag=OptionsFence.MULTIPLE,
        single_options_tag=OptionsFence.SINGLE,
    )
