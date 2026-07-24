"""Secret redaction for audit payloads.

Tool args carry plugin credentials inline (Canvas nests an ``auth`` payload
with an API token; OpenEdx passes username/password and OAuth tokens), so every
payload column (``tool_args``, ``old_values``, ``new_values``) is redacted here
*before* canonicalization and persistence, so unredacted secrets never touch
the database or the canonical bytes. Exception messages are the remaining
free-text path into the store (``error_detail``); :func:`scrub_error_detail`
covers it.
"""

import re
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from sparkth.core.audit.constants import MAX_DEPTH, MAX_ERROR_DETAIL_LENGTH, REDACTED, SECRET_KEYS


def redact(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of ``payload`` with every secret-keyed value replaced.

    The input mapping is never mutated. Matching is by key name only: a key in
    the secret set has its entire value (scalar or subtree) replaced with
    :data:`REDACTED`; all other mappings and lists are traversed recursively,
    down to :data:`MAX_DEPTH` levels (deeper subtrees are replaced wholesale).
    """
    return {key: _redact_value(key, value, MAX_DEPTH) for key, value in payload.items()}


def _redact_value(key: str, value: Any, depth: int) -> Any:
    if key.lower() in SECRET_KEYS:
        return REDACTED
    return _walk(value, depth)


def _walk(value: Any, depth: int) -> Any:
    if isinstance(value, Mapping):
        if depth <= 0:
            return REDACTED
        return {key: _redact_value(key, inner, depth - 1) for key, inner in value.items()}
    if isinstance(value, list):
        if depth <= 0:
            return REDACTED
        return [_walk(item, depth - 1) for item in value]
    return value


# A secret-named key immediately followed by an assignment: `token=...` in a
# URL query, `'api_key': '...'` in a repr'd mapping. The value is everything
# up to the next whitespace; over-redacting a trailing delimiter is fine.
_SECRET_ASSIGNMENT = re.compile(r"(?i)\b(" + "|".join(sorted(SECRET_KEYS)) + r")\b(['\"]?\s*[=:]\s*)\S+")


def scrub_error_detail(exc: BaseException) -> str:
    """Format ``exc`` for the ``error_detail`` column without leaking secrets.

    The key-based payload redaction cannot see into free text, and exception
    messages routinely echo the values it was designed to keep out: Pydantic
    ``ValidationError`` renders the failing ``input_value``, HTTP client
    errors carry tokenized URLs. Validation errors are re-rendered without
    their inputs, secret-keyed assignments in any message are masked, and the
    result is bounded to :data:`MAX_ERROR_DETAIL_LENGTH`.
    """
    if isinstance(exc, ValidationError):
        message = "; ".join(
            f"{'.'.join(str(loc) for loc in error['loc'])}: {error['msg']}"
            for error in exc.errors(include_input=False, include_url=False)
        )
    else:
        message = str(exc)
    message = _SECRET_ASSIGNMENT.sub(rf"\1\2{REDACTED}", message)
    return f"{type(exc).__name__}: {message}"[:MAX_ERROR_DETAIL_LENGTH]
