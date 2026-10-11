"""Which field changes saved learner state cannot survive."""

from collections.abc import Mapping

import pytest

from sparkth.plugins.pxc.field_changes import incompatible_field_changes

QUESTION: dict[str, object] = {"type": "string", "scope": "activity", "default": "What is 2 + 2?"}
ANSWERS: dict[str, object] = {"type": "array", "scope": "user,activity", "items": {"type": "integer"}}
SCORES: dict[str, object] = {"type": "object", "scope": "user,course", "properties": {"best": {"type": "number"}}}
FIELDS = {"question": QUESTION, "answers": ANSWERS, "scores": SCORES}


def test_unchanged_fields_are_compatible() -> None:
    assert incompatible_field_changes(FIELDS, FIELDS) == []


def test_a_changed_default_is_compatible() -> None:
    changed = {**FIELDS, "question": {**QUESTION, "default": "What is 3 + 3?"}}

    assert incompatible_field_changes(FIELDS, changed) == []


def test_an_explicit_null_default_reads_as_no_default() -> None:
    without = {"question": {"type": "string", "scope": "activity"}}
    with_null = {"question": {"type": "string", "scope": "activity", "default": None}}

    assert incompatible_field_changes(without, with_null) == []
    assert incompatible_field_changes(with_null, without) == []


def test_an_added_field_is_compatible() -> None:
    added: dict[str, Mapping[str, object]] = {**FIELDS, "hints_used": {"type": "integer", "scope": "user,activity"}}

    assert incompatible_field_changes(FIELDS, added) == []


@pytest.mark.parametrize(
    ("name", "changed"),
    [
        ("question", {**QUESTION, "type": "integer"}),
        ("question", {**QUESTION, "scope": "user,activity"}),
        ("answers", {**ANSWERS, "items": {"type": "string"}}),
        ("scores", {**SCORES, "properties": {"best": {"type": "integer"}}}),
    ],
)
def test_a_changed_definition_is_reported(name: str, changed: dict[str, object]) -> None:
    changed_fields: dict[str, Mapping[str, object]] = {**FIELDS, name: changed}

    assert incompatible_field_changes(FIELDS, changed_fields) == [f"field {name!r} changed its type, scope or schema"]


def test_a_removed_field_is_reported() -> None:
    removed = {"question": QUESTION, "answers": ANSWERS}

    assert incompatible_field_changes(FIELDS, removed) == ["field 'scores' was removed"]


def test_every_offending_field_is_reported() -> None:
    changed = {"question": {**QUESTION, "type": "integer"}, "answers": ANSWERS}

    assert incompatible_field_changes(FIELDS, changed) == [
        "field 'question' changed its type, scope or schema",
        "field 'scores' was removed",
    ]
