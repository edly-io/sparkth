"""Tests for resolving a CLI scope argument (sparkth/cli/scope_lookup.py).
Authored with LLM (Claude) assistance."""

import pytest
import typer

from sparkth.cli.scope_lookup import resolve_scope, validate_scope_object
from sparkth.lib.permissions.scopes import GLOBAL, PLUGIN, ROLE


def test_resolve_scope_returns_a_registered_scope_kind() -> None:
    assert resolve_scope("global") is GLOBAL


def test_resolve_scope_exits_for_an_unknown_scope_kind(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(typer.Exit) as excinfo:
        resolve_scope("corse")
    assert excinfo.value.exit_code == 1
    assert "Unknown scope kind: 'corse'" in capsys.readouterr().out


def test_validate_scope_object_accepts_a_loaded_plugin() -> None:
    validate_scope_object(PLUGIN, "compose")


def test_validate_scope_object_exits_for_a_plugin_that_is_not_loaded(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(typer.Exit) as excinfo:
        validate_scope_object(PLUGIN, "compoze")
    assert excinfo.value.exit_code == 1
    out = capsys.readouterr().out
    assert "Unknown plugin: 'compoze'" in out
    assert "compose" in out


def test_validate_scope_object_does_not_check_other_scope_kinds() -> None:
    validate_scope_object(ROLE, "999")
    validate_scope_object(GLOBAL, None)
