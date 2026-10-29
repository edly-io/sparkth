"""Tests for scripts/dump_frontend_plugins.py (offline frontend plugin list dump).

The script is the drift gate between the backend's FRONTEND_APPS and icon
declarations and the generated frontend module: the committed file must always match the
script's output, so a declaration change without regeneration is a red build.
Without ``-o`` the dump goes to stdout, which is how it is inspected by hand.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from scripts import dump_frontend_plugins

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "dump_frontend_plugins.py"
GENERATED = REPO_ROOT / "frontend" / "lib" / "plugins" / "generated.ts"


def _run_dump() -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    return result.stdout


@pytest.fixture(scope="module")
def dumps() -> tuple[str, str]:
    """The script's stdout from two separate processes: one to check, one to compare it with."""
    return _run_dump(), _run_dump()


def test_dump_lists_frontend_declaring_plugins_sorted_offline(dumps: tuple[str, str]) -> None:
    assert 'export const FRONTEND_PLUGIN_NAMES = ["compose", "google-drive", "pxc", "slack"] as const;' in dumps[0]


def test_dump_lists_each_plugins_declared_icon_names_once(dumps: tuple[str, str]) -> None:
    """Chat declares "plus" for both its display info and its sidebar entry, and it is listed once."""
    expected = (
        "export const PLUGIN_ICON_NAMES = {\n"
        '  "compose": ["plus"],\n'
        '  "pxc": ["blocks"],\n'
        '  "slack": ["slack"],\n'
        "} as const;\n"
    )
    assert expected in dumps[0]


def test_dump_marks_output_as_generated(dumps: tuple[str, str]) -> None:
    assert "Do not edit" in dumps[0]


def test_dump_output_is_deterministic(dumps: tuple[str, str]) -> None:
    assert dumps[0] == dumps[1]


def test_output_option_writes_the_dump_to_the_given_path(
    tmp_path: Path, dumps: tuple[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "generated.ts"
    dump_frontend_plugins.main(["-o", str(target)])

    assert capsys.readouterr().out == ""
    assert target.read_text() == dumps[0]


def test_output_option_replaces_an_existing_file(tmp_path: Path, dumps: tuple[str, str]) -> None:
    target = tmp_path / "generated.ts"
    target.write_text("stale contents\n")
    dump_frontend_plugins.main(["--output", str(target)])

    assert target.read_text() == dumps[0]


def test_output_option_leaves_the_target_untouched_when_the_dump_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed dump must not clobber the target, as `> file` redirection would."""

    def boom(plugin_name: str) -> bool:
        raise RuntimeError("declarations unavailable")

    monkeypatch.setattr(dump_frontend_plugins, "plugin_has_frontend", boom)

    target = tmp_path / "generated.ts"
    target.write_text("previous contents\n")
    with pytest.raises(RuntimeError):
        dump_frontend_plugins.main(["-o", str(target)])
    assert target.read_text() == "previous contents\n"
    assert list(tmp_path.iterdir()) == [target]


def test_committed_generated_file_is_current(dumps: tuple[str, str]) -> None:
    """The drift gate: frontend/lib/plugins/generated.ts must match the dump.

    Fails when a plugin's FRONTEND_APPS declaration or a declared icon changed
    without running `make frontend.build.plugins`.
    """
    assert GENERATED.read_text() == dumps[0]
