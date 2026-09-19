"""Test environment for the PXC plugin.

``sandbox.wasm`` is a build product, kept out of git (D2), so a clean checkout has none.
``ActivityRuntime`` can be constructed without it — wasmtime is only invoked on the first
sandbox call — so only tests that actually run the sandbox carry the ``wasm`` marker, and
those skip when the binary is absent. CI builds it, so they run there.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sparkth.main import assemble_app
from sparkth.plugins.pxc.activities import activity_dir
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.event_bus import EVENT_BUS

SANDBOX_WASM = activity_dir("mcq") / "sandbox.wasm"

LAUNCH_SECRET = "a-shared-secret-of-at-least-32-bytes"


def pytest_runtest_setup(item: pytest.Item) -> None:
    if "wasm" in item.keywords and not SANDBOX_WASM.exists():
        pytest.skip("sandbox.wasm is not built; run `make pxc.activities.build`")


@pytest.fixture(autouse=True)
def pxc_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Pin every PXC setting so the developer's own env files cannot reach a test.

    ``PxcSettings`` reads ``.env`` and ``.env.local`` like the core settings do, so without
    this a real ``PXC_LAUNCH_SECRET`` would silently become the secret under test and a real
    ``PXC_DATA_DIR`` would have tests writing into the working checkout's state files.
    Environment variables win over both files, so setting them here is what makes a run
    reproducible. The secret starts empty — the fail-closed default; ask for the
    ``configured_secret`` fixture to get a usable one.
    """
    monkeypatch.setenv("PXC_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PXC_LAUNCH_SECRET", "")
    monkeypatch.setenv("PXC_LAUNCH_TOKEN_TTL_SECONDS", "300")
    monkeypatch.setenv("PXC_DEFAULT_ACTIVITY", "mcq")
    get_pxc_settings.cache_clear()
    yield
    get_pxc_settings.cache_clear()


@pytest.fixture
def configured_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    """Configure a launch secret for this test and return it for signing tokens with."""
    monkeypatch.setenv("PXC_LAUNCH_SECRET", LAUNCH_SECRET)
    get_pxc_settings.cache_clear()
    return LAUNCH_SECRET


@pytest.fixture(autouse=True)
def _empty_bus() -> Iterator[None]:
    """Reset the process-wide event bus around every test, so no subscriber leaks into the next."""
    EVENT_BUS._subscribers.clear()
    yield
    EVENT_BUS._subscribers.clear()


@pytest.fixture
def ws_client() -> Iterator[TestClient]:
    """A client that can open WebSockets, which the suite's httpx ``client`` fixture cannot.

    Entered as a context manager so every socket it opens shares one portal, and one event loop.
    """
    with TestClient(assemble_app()) as client:
        yield client
