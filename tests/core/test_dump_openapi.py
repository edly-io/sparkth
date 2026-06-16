"""Tests for scripts/dump_openapi.py (offline OpenAPI schema dump)."""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "dump_openapi.py"

PLUGIN_SENTINEL_PATHS = [
    "/api/v1/chat/completions",
    "/api/v1/slack/oauth/status",
    "/api/v1/google-drive/oauth/status",
]


def _run_dump() -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )
    return result.stdout


def test_dump_outputs_full_schema_offline() -> None:
    schema = json.loads(_run_dump())
    assert schema["openapi"].startswith("3.")
    for path in PLUGIN_SENTINEL_PATHS:
        assert path in schema["paths"]


def test_dump_output_is_deterministic_and_sorted() -> None:
    out = _run_dump()
    assert out == _run_dump()
    schema = json.loads(out)
    assert out == json.dumps(schema, indent=2, sort_keys=True) + "\n"
