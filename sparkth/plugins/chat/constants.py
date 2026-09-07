from pathlib import Path

import anthropic
import httpx
import openai
from google.api_core import exceptions as google_exceptions

from sparkth.lib.i18n import gettext_noop


def get_asset(file_name: str) -> str:
    """Read a prompt asset from assets/, stripped of surrounding whitespace.

    Called at import time: these files are small, and a prompt that fails to load is a broken
    deployment rather than a failed request.
    """
    return (Path(__file__).parent / "assets" / file_name).read_text(encoding="utf-8").strip()


COURSE_DESIGN_SYSTEM_PROMPT = get_asset("course_design_system_prompt.txt")
RAG_CONTEXT_PROMPT = get_asset("rag_context_replacement_prompt.txt")
MESSAGE_SCOPE_CLASSIFIER_SYSTEM_PROMPT = get_asset("message_scope_classifier_system_prompt.txt")
RAG_SEARCH_CLASSIFIER_SYSTEM_PROMPT = get_asset("rag_search_classifier_system_prompt.txt")
LMS_RULES = get_asset("lms_rules_system_prompt.txt")

# How many prior turns reach the scope classifier.
MESSAGE_SCOPE_CLASSIFIER_CONVERSATION_HISTORY = 6

# gettext_noop keeps this a plain str so it can be substituted into the prompt template,
# json.dumps'd onto the SSE stream, and assigned to a pydantic field — none of which a
# LazyString allows. It is rendered with gettext() at each of those boundaries.
REFUSAL_MESSAGE: str = gettext_noop(
    "I'm a course creation assistant and can only help with designing and building "
    "courses. Is there a course you'd like to create?"
)

LLM_PROVIDER_API_ERRORS = (
    anthropic.AuthenticationError,
    anthropic.PermissionDeniedError,
    anthropic.RateLimitError,
    anthropic.BadRequestError,
    anthropic.APIStatusError,
    anthropic.APIConnectionError,
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.RateLimitError,
    openai.BadRequestError,
    openai.APIStatusError,
    openai.APIConnectionError,
    google_exceptions.Unauthenticated,
    google_exceptions.PermissionDenied,
    google_exceptions.ResourceExhausted,
    google_exceptions.InvalidArgument,
    google_exceptions.GoogleAPICallError,
    google_exceptions.ServiceUnavailable,
    httpx.RemoteProtocolError,
)

# Category reported for a tool the registry never discovered. A missing category
# degrades one analytics dimension; it must never break emission.
UNKNOWN_TOOL_CATEGORY = "unknown"
