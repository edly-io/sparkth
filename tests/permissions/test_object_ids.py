"""``to_object_ids`` turns the string object ids of scope grants into integer ids.
Authored with LLM (Claude) assistance."""

from sparkth.core.permissions.utils import to_object_ids


def test_numeric_ids_become_integers() -> None:
    assert to_object_ids({"7", "13"}) == {7, 13}


def test_non_numeric_ids_are_skipped() -> None:
    assert to_object_ids({"7", "x", "1.5", ""}) == {7}


def test_no_restriction_stays_no_restriction() -> None:
    assert to_object_ids(None) is None


def test_no_ids_gives_no_ids() -> None:
    assert to_object_ids(set()) == set()
