"""PXC's :class:`~pxc.lib.field_store.FieldStore` over one SQLite file per activity type.

The file is the activity type's boundary (D1): one file holds every course the type appears in
and every learner who answered, keyed the way PXC's runtime already keys state — by course,
placement and learner. There is no Alembic migration, because these tables are not part of the
application schema.

Values are JSON-encoded rather than stored in typed columns. A field's value may legitimately
be ``null``, and JSON keeps that distinguishable from an absent row; it also keeps arrays and
objects (the sample's ``answers``) in one column.

The connection runs in WAL mode with short transactions (L4): every learner of one activity
type writes to this one file, and WAL is what lets readers proceed while one of them writes.
"""

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from pxc.lib.field_store import FieldStore
from pxc.lib.fields import FieldType

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fields (
    course_id     TEXT NOT NULL,
    activity_name TEXT NOT NULL,
    activity_id   TEXT NOT NULL,
    user_id       TEXT NOT NULL,
    key           TEXT NOT NULL,
    value         TEXT NOT NULL,
    PRIMARY KEY (course_id, activity_name, activity_id, user_id, key)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS field_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id     TEXT NOT NULL,
    activity_name TEXT NOT NULL,
    activity_id   TEXT NOT NULL,
    user_id       TEXT NOT NULL,
    key           TEXT NOT NULL,
    value         TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS field_log_scope
    ON field_log (course_id, activity_name, activity_id, user_id, key, id);
"""

_LOG_WHERE = " WHERE course_id = ? AND activity_name = ? AND activity_id = ? AND user_id = ? AND key = ?"

# SQLite's AUTOINCREMENT ids stop below 2**63, so this is above every id the log can hold.
_NO_CURSOR = 2**63 - 1


def _log_scope(
    course_id: str, activity_name: str, activity_id: str, user_id: str, key: str
) -> tuple[str, str, str, str, str]:
    """The five-column log key, as a parameter tuple."""
    return (course_id, activity_name, activity_id, user_id, key)


class SqliteFieldStore(FieldStore):  # type: ignore[misc]  # pxc-lib ships no py.typed marker
    """Field persistence for one activity type, in one SQLite file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)

    def _connect(self) -> closing[sqlite3.Connection]:
        """A closing context manager over a connection with WAL enabled.

        Opened per operation rather than kept: the store is handed to a runtime built per
        request and used from a worker thread, and a connection is not safe to share across
        threads.

        Wrapped in ``contextlib.closing`` deliberately. ``sqlite3.Connection.__exit__``
        commits or rolls back but **never closes**, and the runtime calls ``get_field`` /
        ``set_field`` on every sandbox host call — so a bare ``with self._connect()`` leaks
        dozens of open connections per action.
        """
        connection = sqlite3.connect(self._path, isolation_level=None)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        return closing(connection)

    def get(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> FieldType | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM fields WHERE course_id = ? AND activity_name = ?"
                " AND activity_id = ? AND user_id = ? AND key = ?",
                (course_id, activity_name, activity_id, user_id, key),
            ).fetchone()
        if row is None:
            return None
        decoded: FieldType = json.loads(row[0])
        return decoded

    def set(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        value: FieldType,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO fields (course_id, activity_name, activity_id, user_id, key, value)"
                " VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT (course_id, activity_name, activity_id, user_id, key)"
                " DO UPDATE SET value = excluded.value",
                (course_id, activity_name, activity_id, user_id, key, json.dumps(value)),
            )

    def delete(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM fields WHERE course_id = ? AND activity_name = ?"
                " AND activity_id = ? AND user_id = ? AND key = ?",
                (course_id, activity_name, activity_id, user_id, key),
            )
            return cursor.rowcount > 0

    def keys(self) -> list[str]:
        """Every stored scalar field, as PXC's composite key strings.

        ``ActivityRuntime`` never calls this; it is part of the ``FieldStore`` interface, and
        the composite form matches what ``MemoryKVStore`` returns so the two are
        interchangeable in a test.
        """
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT activity_name, course_id, activity_id, user_id, key FROM fields"
                " ORDER BY activity_name, course_id, activity_id, user_id, key"
            ).fetchall()
        return [f"pxc.{row[0]}.{row[1]}.{row[2]}.{row[3]}.{row[4]}" for row in rows]

    def log_get(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        entry_id: int,
    ) -> FieldType | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM field_log" + _LOG_WHERE + " AND id = ?",
                (*_log_scope(course_id, activity_name, activity_id, user_id, key), entry_id),
            ).fetchone()
        if row is None:
            return None
        decoded: FieldType = json.loads(row[0])
        return decoded

    def log_get_after(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        after_id: int | None,
        count: int,
    ) -> list[dict[str, Any]]:
        cursor = -1 if after_id is None else after_id
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, value FROM field_log" + _LOG_WHERE + " AND id > ? ORDER BY id ASC LIMIT ?",
                (*_log_scope(course_id, activity_name, activity_id, user_id, key), cursor, count),
            ).fetchall()
        return [{"id": row[0], "value": json.loads(row[1])} for row in rows]

    def log_get_before(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        before_id: int | None,
        count: int,
    ) -> list[dict[str, Any]]:
        # No cursor means "from the newest", so the guard is an id above every real one.
        cursor = _NO_CURSOR if before_id is None else before_id
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, value FROM field_log" + _LOG_WHERE + " AND id < ? ORDER BY id DESC LIMIT ?",
                (*_log_scope(course_id, activity_name, activity_id, user_id, key), cursor, count),
            ).fetchall()
        return [{"id": row[0], "value": json.loads(row[1])} for row in rows]

    def log_append(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        value: FieldType,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO field_log (course_id, activity_name, activity_id, user_id, key, value)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    *_log_scope(course_id, activity_name, activity_id, user_id, key),
                    json.dumps(value),
                ),
            )
        return int(cursor.lastrowid or 0)

    def log_delete(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        entry_id: int,
    ) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM field_log" + _LOG_WHERE + " AND id = ?",
                (*_log_scope(course_id, activity_name, activity_id, user_id, key), entry_id),
            )
            return cursor.rowcount > 0

    def log_delete_before(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        before_id: int,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM field_log" + _LOG_WHERE + " AND id < ?",
                (*_log_scope(course_id, activity_name, activity_id, user_id, key), before_id),
            )
            return cursor.rowcount

    def log_clear(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM field_log" + _LOG_WHERE,
                _log_scope(course_id, activity_name, activity_id, user_id, key),
            )
            return cursor.rowcount
