"""``convert_to_ints`` turns the string ids of scope grants into integer ids.
Authored with LLM (Claude) assistance."""

from sparkth.core.permissions.utils import convert_to_ints


def test_numeric_ids_become_integers() -> None:
    assert convert_to_ints({"7", "13"}) == {7, 13}


def test_non_numeric_ids_are_skipped() -> None:
    assert convert_to_ints({"7", "x", "1.5", ""}) == {7}


def test_no_restriction_stays_no_restriction() -> None:
    assert convert_to_ints(None) is None


def test_no_ids_gives_no_ids() -> None:
    assert convert_to_ints(set()) == set()
