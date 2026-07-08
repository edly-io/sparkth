"""Pinned canonical serialization for audit events.

Every audit row stores the exact bytes this module produced at insert time
(``AuditEvent.canonical_bytes``); the tamper-evidence sealer later hashes those
stored bytes, and verification re-reads them rather than re-serializing the ORM
object. The encoding is therefore pinned forever: sorted keys, no inter-token
whitespace, UTF-8 without ASCII escaping, JSON literals for null/true/false.
Any change to this function invalidates previously stored bytes.

This is an RFC 8785-style canonical form (deterministic key order and spacing),
not a full RFC 8785 implementation: payloads are restricted to JSON-native
Python values, so the number-formatting edge cases JCS exists for do not arise.
"""

import json
from collections.abc import Mapping
from typing import Any


def canonicalize(payload: Mapping[str, Any]) -> bytes:
    """Serialize ``payload`` to its pinned canonical byte form.

    Raises:
        TypeError: ``payload`` contains a value that is not JSON-native
            (only str, int, float, bool, None, mappings, and sequences are
            representable).
        ValueError: ``payload`` contains a non-finite float (NaN/Infinity).
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
