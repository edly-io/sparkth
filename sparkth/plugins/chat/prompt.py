import json
import re
from datetime import datetime
from pathlib import Path
from typing import cast
from uuid import UUID

from sparkth.lib.i18n import gettext_noop
from sparkth.lib.log import get_logger

logger = get_logger(__name__)

_ASSETS_DIR = Path(__file__).parent / "assets"
_scope_cfg: dict[str, object] | None = None


def _load_scope_config() -> dict[str, object]:
    """Load and cache the scope keywords config from assets/scope_keywords.json."""
    global _scope_cfg
    if _scope_cfg is None:
        _scope_cfg = json.loads((_ASSETS_DIR / "scope_keywords.json").read_text(encoding="utf-8"))
    return _scope_cfg


def _load_system_prompt_template() -> str:
    return (_ASSETS_DIR / "system_prompt.txt").read_text(encoding="utf-8").strip()


def get_current_datetime() -> datetime:
    return datetime.now()


# Load once at import time — small local files, no I/O on each request
_SYSTEM_PROMPT_TEMPLATE: str = _load_system_prompt_template()
_cfg = _load_scope_config()
# User-facing copy lives here rather than in scope_keywords.json because pybabel extracts
# from Python source only; the keyword lists stay in the asset, as they are data, not copy.
# gettext_noop keeps this a plain str so it can be substituted into the prompt template,
# json.dumps'd onto the SSE stream, and assigned to a pydantic field — none of which a
# LazyString allows. It is rendered with gettext() at each of those boundaries.
REFUSAL_MESSAGE: str = gettext_noop(
    "I'm a course creation assistant and can only help with designing and building "
    "courses. Is there a course you'd like to create?"
)
_IN_SCOPE_KEYWORDS: frozenset[str] = frozenset(cast(list[str], _cfg["in_scope"]))
_OUT_OF_SCOPE_KEYWORDS: frozenset[str] = frozenset(cast(list[str], _cfg["out_of_scope"]))

# Word-boundary patterns compiled once at import time — avoids per-request compilation
# and prevents substring collisions (e.g. "code" matching "barcode"). Each pattern is
# paired with its keyword so a refusal can report which keyword triggered it.
_IN_SCOPE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (kw, re.compile(r"\b" + re.escape(kw) + r"\b")) for kw in _IN_SCOPE_KEYWORDS
]
_OUT_OF_SCOPE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (kw, re.compile(r"\b" + re.escape(kw) + r"\b")) for kw in _OUT_OF_SCOPE_KEYWORDS
]


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


def is_query_in_scope(query: str, conversation_uuid: UUID | None = None) -> bool:
    """Check if a query is related to course creation (in-scope).

    Keywords are loaded from assets/scope_keywords.json at import time.
    Returns True if in-scope (or empty — let the LLM's system prompt handle it),
    False if clearly out-of-scope (general knowledge, code, personal advice, etc.).

    A refusal is logged at warning level with the keywords that matched, because this
    check runs before any model call and is otherwise untraceable.

    Args:
        query: The user's message.
        conversation_uuid: Conversation the message belongs to, logged on a refusal so it
            can be traced to a thread. ``None`` on the first message of a new chat, which
            is checked before any conversation row exists.
    """
    if not query:
        return True

    query_lower = query.lower()

    has_in_scope = any(p.search(query_lower) for _, p in _IN_SCOPE_PATTERNS)
    has_out_of_scope = any(p.search(query_lower) for _, p in _OUT_OF_SCOPE_PATTERNS)

    if has_out_of_scope and not has_in_scope:
        # The only trace of this refusal: the LLM classifier is short-circuited and the
        # chat model is never called, so nothing downstream records the decision. The
        # matched keywords are re-collected here rather than above so the full pattern
        # scan is paid only on the rare refusal, not on every passing message.
        # Keywords and length only — the message itself may hold course content.
        logger.warning(
            "Keyword scope filter refused a message: out-of-scope keyword(s) %s matched, "
            "no in-scope keyword present (conversation_uuid=%s query_len=%d)",
            sorted(kw for kw, p in _OUT_OF_SCOPE_PATTERNS if p.search(query_lower)),
            conversation_uuid,
            len(query),
        )
        return False

    if has_in_scope:
        return True

    # Default to in-scope — let the LLM's system prompt handle the refusal
    return True
