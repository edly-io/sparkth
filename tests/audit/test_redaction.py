"""Secrets must never reach the audit table: tool args carry plugin credentials
inline (Canvas nests an `auth` payload with an api_token; OpenEdx passes
username/password), so the redactor strips them before persistence. Exception
messages are the other leak path (`error_detail` is free text: Pydantic echoes
failing inputs, HTTP errors carry tokenized URLs), scrubbed by
`scrub_error_detail`."""

from pydantic import BaseModel, ValidationError

from sparkth.core.audit.constants import MAX_DEPTH, MAX_ERROR_DETAIL_LENGTH, REDACTED
from sparkth.core.audit.redaction import redact, scrub_error_detail


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


class _Course(BaseModel):
    course_id: int


def _validation_error() -> ValidationError:
    try:
        _Course.model_validate({"course_id": "hunter2-token-value"})
    except ValidationError as exc:
        return exc
    raise AssertionError("validation must fail")


def test_error_detail_keeps_exception_type_and_message() -> None:
    assert scrub_error_detail(ValueError("bad course id")) == "ValueError: bad course id"


def test_error_detail_validation_error_inputs_are_omitted() -> None:
    detail = scrub_error_detail(_validation_error())
    assert detail.startswith("ValidationError: ")
    assert "course_id" in detail
    assert "hunter2-token-value" not in detail


def test_error_detail_secret_url_parameters_are_masked() -> None:
    detail = scrub_error_detail(RuntimeError("GET https://lms.example.com/api?token=s3cret failed"))
    assert "s3cret" not in detail
    assert REDACTED in detail


def test_error_detail_quoted_secret_keys_are_masked() -> None:
    detail = scrub_error_detail(RuntimeError("request failed with {'api_key': 'abc123', 'course_id': 5}"))
    assert "abc123" not in detail
    assert "course_id" in detail


def test_error_detail_is_length_bounded() -> None:
    detail = scrub_error_detail(RuntimeError("x" * (MAX_ERROR_DETAIL_LENGTH * 2)))
    assert len(detail) <= MAX_ERROR_DETAIL_LENGTH
