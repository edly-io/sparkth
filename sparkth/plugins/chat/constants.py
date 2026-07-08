from pathlib import Path

import anthropic
import httpx
import openai
from google.api_core import exceptions as google_exceptions

RAG_CONTEXT_PROMPT = (Path(__file__).parent / "assets" / "rag_context_replacement_prompt.txt").read_text()

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

LMS_RULES = (Path(__file__).parent / "assets" / "lms_rules_system_prompt.txt").read_text()
