"""The canonicalizer must produce byte-identical output for semantically equal
payloads: the bytes it emits are stored on every audit row (`canonical_bytes`)
and later hashed by the tamper-evidence sealer, so any nondeterminism here
would make an honest row read as tampered."""

import pytest

from app.core.audit.canonical import canonicalize


def test_key_order_does_not_change_bytes() -> None:
    assert canonicalize({"b": 2, "a": 1}) == canonicalize({"a": 1, "b": 2})


def test_golden_vector() -> None:
    assert canonicalize({"b": 2, "a": "x"}) == b'{"a":"x","b":2}'


def test_nested_mappings_are_sorted_recursively() -> None:
    assert canonicalize({"outer": {"z": 1, "a": 2}}) == b'{"outer":{"a":2,"z":1}}'


def test_no_whitespace_between_tokens() -> None:
    assert b" " not in canonicalize({"a": [1, 2], "b": {"c": True}})


def test_non_ascii_is_utf8_not_escaped() -> None:
    assert canonicalize({"a": "é"}) == '{"a":"é"}'.encode()


def test_none_true_false_use_json_literals() -> None:
    assert canonicalize({"a": None, "b": True, "c": False}) == b'{"a":null,"b":true,"c":false}'


def test_non_json_value_is_rejected() -> None:
    with pytest.raises(TypeError):
        canonicalize({"a": object()})
