from datetime import datetime
from pathlib import Path

from sparkth.lib.i18n import gettext_noop

_ASSETS_DIR = Path(__file__).parent / "assets"


def _load_system_prompt_template() -> str:
    return (_ASSETS_DIR / "system_prompt.txt").read_text(encoding="utf-8").strip()


def get_current_datetime() -> datetime:
    return datetime.now()


# Loaded once at import time — a small local file, no I/O on each request
_SYSTEM_PROMPT_TEMPLATE: str = _load_system_prompt_template()
# gettext_noop keeps this a plain str so it can be substituted into the prompt template,
# json.dumps'd onto the SSE stream, and assigned to a pydantic field — none of which a
# LazyString allows. It is rendered with gettext() at each of those boundaries.
REFUSAL_MESSAGE: str = gettext_noop(
    "I'm a course creation assistant and can only help with designing and building "
    "courses. Is there a course you'd like to create?"
)


def get_learning_design_system_prompt() -> str:
    """Render the learning-design system prompt.

    No language is injected. The template's OUTPUT LANGUAGE section instructs the model to
    write in the language of the user's most recent message and to switch when the user
    does, so the output language is inferred from the conversation rather than resolved
    from stored state.

    A language change takes effect on the very next turn because the model reads the user's
    latest message, not because of anything this render does: ``current_datetime`` is the
    only substitution that varies per request, and the refusal sentence is a constant.
    Earlier turns are left as they were.
    """
    return _SYSTEM_PROMPT_TEMPLATE.format(
        current_datetime=get_current_datetime(),
        refusal_message=REFUSAL_MESSAGE,
    )
