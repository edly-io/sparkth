"""Tests for scripts/dump_frontend_plugins.py (offline frontend plugin list dump).

The script is the drift gate between the backend's FRONTEND_APPS declarations
and the generated frontend module: the committed file must always match the
script's output, so a declaration change without regeneration is a red build.
Without ``-o`` the dump goes to stdout, which is how it is inspected by hand.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "dump_frontend_plugins.py"
GENERATED = REPO_ROOT / "frontend" / "lib" / "plugins" / "generated.ts"


def _run_dump(*args: str) -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    return result.stdout


def test_dump_lists_frontend_declaring_plugins_sorted_offline() -> None:
    out = _run_dump()
    assert 'export const FRONTEND_PLUGIN_NAMES = ["chat", "google-drive", "slack"] as const;' in out


def test_dump_marks_output_as_generated() -> None:
    assert "Do not edit" in _run_dump()


def test_dump_output_is_deterministic() -> None:
    assert _run_dump() == _run_dump()


def test_output_option_writes_the_dump_to_the_given_path(tmp_path: Path) -> None:
    target = tmp_path / "generated.ts"
    assert _run_dump("-o", str(target)) == ""
    assert target.read_text() == _run_dump()


def test_output_option_replaces_an_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "generated.ts"
    target.write_text("stale contents\n")
    _run_dump("--output", str(target))
    assert target.read_text() == _run_dump()


def test_output_option_leaves_the_target_untouched_when_the_dump_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed dump must not clobber the target, as `> file` redirection would."""
    from scripts import dump_frontend_plugins

    def boom(plugin_name: str) -> bool:
        raise RuntimeError("declarations unavailable")

    monkeypatch.setattr(dump_frontend_plugins, "plugin_has_frontend", boom)

    target = tmp_path / "generated.ts"
    target.write_text("previous contents\n")
    with pytest.raises(RuntimeError):
        dump_frontend_plugins.main(["-o", str(target)])
    assert target.read_text() == "previous contents\n"
    assert list(tmp_path.iterdir()) == [target]


def test_committed_generated_file_is_current() -> None:
    """The drift gate: frontend/lib/plugins/generated.ts must match the dump.

    Fails when a plugin's FRONTEND_APPS declaration changed without running
    `make frontend.build.plugins`.
    """
    assert GENERATED.read_text() == _run_dump()
