import json
import re
from datetime import datetime
from pathlib import Path
from typing import cast

from sparkth.lib.i18n import gettext_noop

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
# and prevents substring collisions (e.g. "code" matching "barcode").
_IN_SCOPE_PATTERNS: list[re.Pattern[str]] = [re.compile(r"\b" + re.escape(kw) + r"\b") for kw in _IN_SCOPE_KEYWORDS]
_OUT_OF_SCOPE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b" + re.escape(kw) + r"\b") for kw in _OUT_OF_SCOPE_KEYWORDS
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


def is_query_in_scope(query: str) -> bool:
    """Check if a query is related to course creation (in-scope).

    Keywords are loaded from assets/scope_keywords.json at import time.
    Returns True if in-scope (or empty — let the LLM's system prompt handle it),
    False if clearly out-of-scope (general knowledge, code, personal advice, etc.).
    """
    if not query:
        return True

    query_lower = query.lower()

    has_in_scope = any(p.search(query_lower) for p in _IN_SCOPE_PATTERNS)
    has_out_of_scope = any(p.search(query_lower) for p in _OUT_OF_SCOPE_PATTERNS)

    if has_out_of_scope and not has_in_scope:
        return False

    if has_in_scope:
        return True

    # Default to in-scope — let the LLM's system prompt handle the refusal
    return True
