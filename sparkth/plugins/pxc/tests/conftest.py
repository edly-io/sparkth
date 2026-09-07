"""Test environment for the PXC plugin.

``sandbox.wasm`` is a build product, kept out of git (D2), so a clean checkout has none.
``ActivityRuntime`` can be constructed without it — wasmtime is only invoked on the first
sandbox call — so only tests that actually run the sandbox carry the ``wasm`` marker, and
those skip when the binary is absent. CI builds it, so they run there.
"""

import pytest

from sparkth.plugins.pxc.activities import activity_dir

SANDBOX_WASM = activity_dir("mcq") / "sandbox.wasm"


def pytest_runtest_setup(item: pytest.Item) -> None:
    if "wasm" in item.keywords and not SANDBOX_WASM.exists():
        pytest.skip("sandbox.wasm is not built; run `make pxc.activity.build`")
