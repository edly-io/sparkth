"""Tests for resolving a CLI scope argument (sparkth/cli/scope_lookup.py).
Authored with LLM (Claude) assistance."""

import pytest
import typer

from sparkth.cli.scope_lookup import resolve_scope
from sparkth.lib.permissions.scopes import GLOBAL


def test_resolve_scope_returns_a_registered_scope_kind() -> None:
    assert resolve_scope("global") is GLOBAL


def test_resolve_scope_exits_for_an_unknown_scope_kind(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(typer.Exit) as excinfo:
        resolve_scope("corse")
    assert excinfo.value.exit_code == 1
    assert "Unknown scope kind: 'corse'" in capsys.readouterr().out
