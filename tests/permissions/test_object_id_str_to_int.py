"""``object_id_str_to_int`` turns the string ids of scope grants into integer ids.
Authored with LLM (Claude) assistance."""

from sparkth.core.permissions.dependencies import object_id_str_to_int


def test_numeric_ids_become_integers() -> None:
    assert object_id_str_to_int({"7", "13"}) == {7, 13}


def test_non_numeric_ids_are_skipped() -> None:
    assert object_id_str_to_int({"7", "x", "1.5", ""}) == {7}


def test_no_restriction_stays_no_restriction() -> None:
    assert object_id_str_to_int(None) is None


def test_no_ids_gives_no_ids() -> None:
    assert object_id_str_to_int(set()) == set()
