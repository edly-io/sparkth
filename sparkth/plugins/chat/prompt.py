from datetime import datetime

from sparkth.plugins.chat.constants import COURSE_DESIGN_SYSTEM_PROMPT, REFUSAL_MESSAGE


def get_course_design_system_prompt() -> str:
    """Render the course-design system prompt.

    No language is injected. The template's OUTPUT LANGUAGE section instructs the model to
    write in the language of the user's most recent message and to switch when the user
    does, so the output language is inferred from the conversation rather than resolved
    from stored state.

    A language change takes effect on the very next turn because the model reads the user's
    latest message, not because of anything this render does: the date is the only
    substitution that varies per request, and the refusal sentence is a constant. Earlier
    turns are left as they were.
    """
    return COURSE_DESIGN_SYSTEM_PROMPT.format(
        current_datetime=datetime.now(),
        refusal_message=REFUSAL_MESSAGE,
    )
