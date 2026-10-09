"""The smoke test the builder runs in a child process."""

from pathlib import Path

import pytest

from sparkth.plugins.pxc.activities import activity_dir
from sparkth.plugins.pxc.smoke import main


@pytest.mark.wasm
def test_the_bundled_sample_passes_the_smoke_test() -> None:
    assert main([str(activity_dir("mcq"))]) == 0


def test_a_sandbox_that_cannot_run_fails_the_smoke_test(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    directory = tmp_path / "activity"
    directory.mkdir()
    (directory / "manifest.json").write_text((activity_dir("mcq") / "manifest.json").read_text())
    (directory / "sandbox.wasm").write_bytes(b"not a component")

    assert main([str(directory)]) == 1
    assert "get_state failed" in capsys.readouterr().err
