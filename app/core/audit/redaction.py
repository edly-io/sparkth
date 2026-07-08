"""Secret redaction for audit payloads.

Tool args carry plugin credentials inline (Canvas nests an ``auth`` payload
with an API token; OpenEdx passes username/password and OAuth tokens), so every
payload column (``tool_args``, ``old_values``, ``new_values``) is redacted here
*before* canonicalization and persistence, so unredacted secrets never touch
the database or the canonical bytes.
"""

from collections.abc import Mapping
from typing import Any

from app.core.audit.constants import MAX_DEPTH, REDACTED, SECRET_KEYS


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
