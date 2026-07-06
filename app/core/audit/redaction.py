"""Secret redaction for audit payloads.

Tool args carry plugin credentials inline (Canvas nests an ``auth`` payload
with an API token; OpenEdx passes username/password and OAuth tokens), so every
payload column (``tool_args``, ``old_values``, ``new_values``) is redacted here
*before* canonicalization and persistence, so unredacted secrets never touch
the database or the canonical bytes.
"""

from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"

# Containers nested deeper than this are replaced with REDACTED wholesale.
# Payloads are attacker-influenceable (LLM/plugin-generated tool args), and an
# unbounded recursive walk would hit the interpreter recursion limit around
# depth ~500, far below what json.loads accepts. Real payloads are a few
# levels deep; replacing (rather than raising) guarantees nothing unscanned
# is ever persisted while keeping the audited action alive.
MAX_DEPTH = 64

# Keys whose value is replaced wholesale, matched case-insensitively at any depth.
# "auth" covers the credential sub-objects plugins nest into tool args.
_SECRET_KEYS = frozenset(
    {
        "auth",
        "authorization",
        "password",
        "passwd",
        "secret",
        "client_secret",
        "token",
        "api_token",
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "private_key",
    }
)


def redact(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of ``payload`` with every secret-keyed value replaced.

    The input mapping is never mutated. Matching is by key name only: a key in
    the secret set has its entire value (scalar or subtree) replaced with
    :data:`REDACTED`; all other mappings and lists are traversed recursively,
    down to :data:`MAX_DEPTH` levels (deeper subtrees are replaced wholesale).
    """
    return {key: _redact_value(key, value, MAX_DEPTH) for key, value in payload.items()}


def _redact_value(key: str, value: Any, depth: int) -> Any:
    if key.lower() in _SECRET_KEYS:
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
