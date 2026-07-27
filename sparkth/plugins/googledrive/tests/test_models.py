"""Unit tests for Google Drive model column mappings."""

import pytest
from sqlmodel import SQLModel

from sparkth.lib.models import TZDateTime

TIMEZONE_AWARE_COLUMNS = [
    ("drive_oauth_tokens", "token_expiry"),
    ("drive_folders", "last_synced_at"),
    ("drive_files", "last_synced_at"),
    ("drive_files", "modified_time"),
]


@pytest.mark.parametrize(("table_name", "column_name"), TIMEZONE_AWARE_COLUMNS)
def test_datetime_columns_are_timezone_aware(table_name: str, column_name: str) -> None:
    """Drive datetime columns must be TZDateTime (timestamptz): the plugin writes
    aware UTC datetimes (and Google's API returns aware timestamps), asyncpg
    rejects aware values on a TIMESTAMP WITHOUT TIME ZONE column, and SQLite
    drops the offset on storage so reads must be re-tagged as UTC."""
    column_type = SQLModel.metadata.tables[table_name].columns[column_name].type

    assert isinstance(column_type, TZDateTime)
