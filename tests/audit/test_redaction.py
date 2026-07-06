"""Secrets must never reach the audit table: tool args carry plugin credentials
inline (Canvas nests an `auth` payload with an api_token; OpenEdx passes
username/password), so the redactor strips them before persistence."""

from app.core.audit.redaction import MAX_DEPTH, REDACTED, redact


def test_auth_subtree_is_redacted_wholesale() -> None:
    payload = {"auth": {"api_url": "https://x", "api_token": "s3cret"}, "course_id": 5}
    assert redact(payload) == {"auth": REDACTED, "course_id": 5}


def test_secret_key_names_are_redacted_at_any_depth() -> None:
    payload = {"outer": {"password": "p", "api_token": "t", "safe": 1}}
    assert redact(payload) == {"outer": {"password": REDACTED, "api_token": REDACTED, "safe": 1}}


def test_secret_key_match_is_case_insensitive() -> None:
    assert redact({"Authorization": "Bearer x"}) == {"Authorization": REDACTED}


def test_lists_are_traversed() -> None:
    payload = {"items": [{"secret": "x"}, {"safe": 1}]}
    assert redact(payload) == {"items": [{"secret": REDACTED}, {"safe": 1}]}


def test_non_secret_values_pass_through_unchanged() -> None:
    payload = {"name": "course", "count": 3, "flag": True, "none": None}
    assert redact(payload) == payload


def test_original_mapping_is_not_mutated() -> None:
    payload = {"auth": {"api_token": "s3cret"}}
    redact(payload)
    assert payload == {"auth": {"api_token": "s3cret"}}


def test_deep_nesting_does_not_hit_the_recursion_limit() -> None:
    payload: dict[str, object] = {"leaf": 1}
    for _ in range(5000):
        payload = {"level": payload}
    redacted = redact(payload)  # must not raise RecursionError
    assert redacted["level"] is not None


def test_subtrees_beyond_the_depth_cap_are_redacted_wholesale() -> None:
    payload: dict[str, object] = {"leaf": 1}
    for _ in range(MAX_DEPTH + 5):
        payload = {"level": payload}

    node: object = redact(payload)
    depth = 0
    while isinstance(node, dict):
        node = node["level"] if "level" in node else node.get("leaf")
        depth += 1
    assert node == REDACTED
    assert depth <= MAX_DEPTH + 1


def test_nesting_within_the_depth_cap_passes_through() -> None:
    payload: dict[str, object] = {"leaf": 1}
    for _ in range(10):
        payload = {"level": payload}
    assert redact(payload) == payload
