"""Tests for :class:`~sparkth.plugins.pxc.field_store.SqliteFieldStore`."""

import sqlite3
from pathlib import Path

import pytest

from sparkth.plugins.pxc.field_store import SqliteFieldStore

SCOPE = ("course-v1:X+Y+Z", "mcq", "placement-1", "learner-7")


@pytest.fixture
def store(tmp_path: Path) -> SqliteFieldStore:
    return SqliteFieldStore(tmp_path / "mcq.sqlite3")


def test_an_unset_field_reads_as_none(store: SqliteFieldStore) -> None:
    assert store.get(*SCOPE, "question") is None


def test_a_set_field_reads_back(store: SqliteFieldStore) -> None:
    store.set(*SCOPE, "question", "What is 2 + 2?")

    assert store.get(*SCOPE, "question") == "What is 2 + 2?"


def test_setting_twice_replaces_rather_than_duplicates(store: SqliteFieldStore) -> None:
    store.set(*SCOPE, "question", "first")
    store.set(*SCOPE, "question", "second")

    assert store.get(*SCOPE, "question") == "second"


def test_structured_values_survive_a_round_trip(store: SqliteFieldStore) -> None:
    store.set(*SCOPE, "answers", ["a", "b"])
    store.set(*SCOPE, "correct_answers", [1])

    assert store.get(*SCOPE, "answers") == ["a", "b"]
    assert store.get(*SCOPE, "correct_answers") == [1]


def test_a_stored_none_is_not_an_unset_field(store: SqliteFieldStore) -> None:
    store.set(*SCOPE, "question", None)

    assert store.get(*SCOPE, "question") is None
    assert "question" in "".join(store.keys())


def test_one_learners_value_does_not_answer_for_another(store: SqliteFieldStore) -> None:
    store.set(*SCOPE, "question", "mine")
    store.set("course-v1:X+Y+Z", "mcq", "placement-1", "learner-8", "question", "theirs")

    assert store.get(*SCOPE, "question") == "mine"


def test_deleting_reports_whether_anything_was_there(store: SqliteFieldStore) -> None:
    store.set(*SCOPE, "question", "q")

    assert store.delete(*SCOPE, "question") is True
    assert store.delete(*SCOPE, "question") is False
    assert store.get(*SCOPE, "question") is None


def test_keys_lists_the_stored_composite_keys(store: SqliteFieldStore) -> None:
    store.set(*SCOPE, "question", "q")

    assert store.keys() == ["pxc.mcq.course-v1:X+Y+Z.placement-1.learner-7.question"]


def test_the_file_is_opened_in_wal_mode(store: SqliteFieldStore, tmp_path: Path) -> None:
    # Asserts the pragma, not the presence of a `-wal` sidecar file: SQLite removes that file
    # on a clean last-close, and the store closes every connection it opens, so a file check
    # would be a race.
    store.set(*SCOPE, "question", "q")
    with sqlite3.connect(tmp_path / "mcq.sqlite3") as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_appending_returns_increasing_entry_ids(store: SqliteFieldStore) -> None:
    first = store.log_append(*SCOPE, "events", {"n": 1})
    second = store.log_append(*SCOPE, "events", {"n": 2})

    assert second > first


def test_an_appended_entry_reads_back_by_id(store: SqliteFieldStore) -> None:
    entry_id = store.log_append(*SCOPE, "events", {"n": 1})

    assert store.log_get(*SCOPE, "events", entry_id) == {"n": 1}


def test_log_get_after_returns_ascending_entries_past_the_cursor(store: SqliteFieldStore) -> None:
    first = store.log_append(*SCOPE, "events", {"n": 1})
    store.log_append(*SCOPE, "events", {"n": 2})
    store.log_append(*SCOPE, "events", {"n": 3})

    assert [entry["value"] for entry in store.log_get_after(*SCOPE, "events", first, 10)] == [
        {"n": 2},
        {"n": 3},
    ]


def test_log_get_after_honours_the_count(store: SqliteFieldStore) -> None:
    store.log_append(*SCOPE, "events", {"n": 1})
    store.log_append(*SCOPE, "events", {"n": 2})

    assert len(store.log_get_after(*SCOPE, "events", None, 1)) == 1


def test_log_get_before_returns_descending_entries(store: SqliteFieldStore) -> None:
    store.log_append(*SCOPE, "events", {"n": 1})
    store.log_append(*SCOPE, "events", {"n": 2})
    last = store.log_append(*SCOPE, "events", {"n": 3})

    assert [entry["value"] for entry in store.log_get_before(*SCOPE, "events", last, 10)] == [
        {"n": 2},
        {"n": 1},
    ]


def test_deleting_an_entry_reports_whether_it_existed(store: SqliteFieldStore) -> None:
    entry_id = store.log_append(*SCOPE, "events", {"n": 1})

    assert store.log_delete(*SCOPE, "events", entry_id) is True
    assert store.log_delete(*SCOPE, "events", entry_id) is False


def test_log_delete_before_returns_how_many_it_removed(store: SqliteFieldStore) -> None:
    store.log_append(*SCOPE, "events", {"n": 1})
    store.log_append(*SCOPE, "events", {"n": 2})
    last = store.log_append(*SCOPE, "events", {"n": 3})

    assert store.log_delete_before(*SCOPE, "events", last) == 2
    assert len(store.log_get_after(*SCOPE, "events", None, 10)) == 1


def test_log_clear_empties_only_this_learners_log(store: SqliteFieldStore) -> None:
    store.log_append(*SCOPE, "events", {"n": 1})
    store.log_append("course-v1:X+Y+Z", "mcq", "placement-1", "learner-8", "events", {"n": 9})

    assert store.log_clear(*SCOPE, "events") == 1
    assert len(store.log_get_after("course-v1:X+Y+Z", "mcq", "placement-1", "learner-8", "events", None, 10)) == 1
