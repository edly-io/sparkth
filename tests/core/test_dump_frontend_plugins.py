"""Tests for scripts/dump_frontend_plugins.py (offline frontend plugin list dump).

The script is the drift gate between the backend's FRONTEND_APPS declarations
and the generated frontend module: the committed file must always match the
script's output, so a declaration change without regeneration is a red build.
"""

import subprocess
import sys
from pathlib import Path

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


def test_dump_lists_frontend_declaring_plugins_sorted_offline() -> None:
    out = _run_dump()
    assert 'export const FRONTEND_PLUGIN_NAMES = ["chat", "google-drive", "slack"] as const;' in out


def test_dump_marks_output_as_generated() -> None:
    assert "Do not edit" in _run_dump()


def test_dump_output_is_deterministic() -> None:
    assert _run_dump() == _run_dump()


def test_committed_generated_file_is_current() -> None:
    """The drift gate: frontend/lib/plugins/generated.ts must match the dump.

    Fails when a plugin's FRONTEND_APPS declaration changed without running
    `make frontend.build.plugins`.
    """
    assert GENERATED.read_text() == _run_dump()
