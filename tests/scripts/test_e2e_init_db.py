"""Tests for scripts/e2e_init_db.py, the ephemeral E2E schema builder."""

from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlmodel import SQLModel

from scripts.e2e_init_db import init_schema


def test_init_schema_builds_the_whole_declared_schema(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'e2e.db'}")
    init_schema(engine)
    # create_all must materialise every table the app declares (core models
    # plus every plugin's, registered by init_schema via get_plugin_loader).
    created = set(inspect(engine).get_table_names())
    assert created == set(SQLModel.metadata.tables)
    assert created  # guard against a no-op / empty metadata


def test_init_schema_is_idempotent(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'e2e.db'}")
    init_schema(engine)
    init_schema(engine)  # second run is a no-op, must not raise
    assert inspect(engine).get_table_names()
