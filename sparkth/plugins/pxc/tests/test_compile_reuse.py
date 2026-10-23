"""The opt-in ``reused_compiles`` fixture reuses a successful compile of the same source."""

import uuid
from pathlib import Path

import pytest

from sparkth.plugins.pxc import builder
from sparkth.plugins.pxc.activities import activity_dir
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.exceptions import PxcCompileFailed

SAMPLE_JS = (activity_dir("mcq") / "sandbox.js").read_text()
BROKEN_JS = "export function onAction( {"

pytestmark = pytest.mark.usefixtures("reused_compiles")


def _counting_node(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Record every toolchain run while still running it."""
    runs: list[list[str]] = []
    real = builder.run_bounded

    async def counted(argv: list[str], cwd: Path, step: str) -> tuple[int, str]:
        runs.append(argv)
        return await real(argv, cwd, step)

    monkeypatch.setattr(builder, "run_bounded", counted)
    return runs


async def _compile(source: str, tmp_path: Path, name: str) -> Path:
    compile_dir = tmp_path / f"{name}-src"
    compile_dir.mkdir()
    output = tmp_path / name / "sandbox.wasm"
    output.parent.mkdir()
    await builder.compile_sandbox(source, compile_dir.resolve(), output)
    return output


@pytest.mark.wasm
async def test_the_same_source_compiles_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runs = _counting_node(monkeypatch)
    # A source no other test compiles, so the store can't hold it yet.
    source = f"{SAMPLE_JS}\n// {uuid.uuid4()}\n"

    first = await _compile(source, tmp_path, "first")
    second = await _compile(source, tmp_path, "second")

    assert len(runs) == 1
    assert second.read_bytes() == first.read_bytes()


@pytest.mark.wasm
async def test_a_reused_compile_brings_its_precompiled_bin(tmp_path: Path) -> None:
    await _compile(SAMPLE_JS, tmp_path, "first")
    second = await _compile(SAMPLE_JS, tmp_path, "second")

    bin_file = second.with_name("sandbox.wasm.bin")
    assert bin_file.exists()
    assert bin_file.stat().st_mtime > second.stat().st_mtime


@pytest.mark.wasm
async def test_a_failed_compile_is_not_reused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runs = _counting_node(monkeypatch)

    for name in ("first", "second"):
        with pytest.raises(PxcCompileFailed):
            await _compile(BROKEN_JS, tmp_path, name)

    assert len(runs) == 2


@pytest.mark.wasm
async def test_a_compile_under_another_toolchain_is_not_reused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    await _compile(SAMPLE_JS, tmp_path, "first")

    monkeypatch.setenv("PXC_TOOLCHAIN_DIR", str(tmp_path / "no-toolchain"))
    get_pxc_settings.cache_clear()

    with pytest.raises(PxcCompileFailed, match="toolchain is not installed"):
        await _compile(SAMPLE_JS, tmp_path, "second")
