"""Test environment for the PXC plugin.

``sandbox.wasm`` is a build product, kept out of git (D2), so a clean checkout has none.
``ActivityRuntime`` can be constructed without it — wasmtime is only invoked on the first
sandbox call — so only tests that actually run the sandbox carry the ``wasm`` marker, and
those skip when the binary is absent. CI builds it, so they run there. Tests that compile an
activity carry the same marker, since `make pxc.activities.build` installs the toolchain they
need along with the binary.
"""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.user import User
from sparkth.lib.auth import bind_current_user_id
from sparkth.main import assemble_app
from sparkth.plugins.pxc.activities import activity_dir, generated_activity_dir
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.event_bus import EVENT_BUS
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.schemas import ActivityConfig
from sparkth.plugins.pxc.store import insert_activity

SANDBOX_WASM = activity_dir("mcq") / "sandbox.wasm"
TOOLCHAIN_DIR = Path(__file__).parent.parent / "builder" / "toolchain"
COMPONENTIZE_JS = TOOLCHAIN_DIR / "node_modules" / ".bin" / "componentize-js"

AUTHORED_MANIFEST = {"name": "placeholder", "ui": "ui.js", "sandbox": "sandbox.wasm"}
AUTHORED_UI_JS = "export function setup(activity) {}\n"
AUTHORED_SANDBOX_JS = 'export function getState(context, permission) { return "{}"; }\n'

LAUNCH_SECRET = "a-shared-secret-of-at-least-32-bytes"


def inline_config(html: str) -> ActivityConfig:
    """The configuration the embed route inlined into this page, parsed as the client parses it."""
    script = html.split('<script type="application/json">')[1].split("</script>")[0]
    return ActivityConfig.model_validate_json(script)


def pytest_runtest_setup(item: pytest.Item) -> None:
    if "wasm" in item.keywords and not (SANDBOX_WASM.exists() and COMPONENTIZE_JS.exists()):
        pytest.skip("the PXC activity toolchain is not installed; run `make pxc.activities.build`")


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
    monkeypatch.setenv("PXC_TOOLCHAIN_DIR", str(TOOLCHAIN_DIR))
    monkeypatch.setenv("PXC_BUILD_TIMEOUT_SECONDS", "120")
    monkeypatch.setenv("PXC_BUILD_CONCURRENCY", "2")
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


def act_as(user: User) -> None:
    """Bind ``user`` as the authenticated caller for the rest of this test."""
    assert user.id is not None
    bind_current_user_id(user.id)


@pytest.fixture
async def authors(session: AsyncSession) -> tuple[User, User]:
    """Two committed users: the first owns ``authored_activity``, the second owns nothing."""
    owner = User(name="Owner", username="owner", email="owner@example.com", hashed_password="x")
    other = User(name="Other", username="other", email="other@example.com", hashed_password="x")
    session.add_all([owner, other])
    await session.commit()
    return owner, other


@pytest.fixture
async def authored_activity(session: AsyncSession, authors: tuple[User, User]) -> PxcActivity:
    """One generated activity owned by the first author, with its row committed and its files on disk.

    Committed because the tools under test read through their own session. The files sit under
    the ``pxc_settings`` fixture's data directory.
    """
    owner, _ = authors
    assert owner.id is not None
    activity = PxcActivity(owner_user_id=owner.id, title="Capital cities", description="Match countries to capitals")
    await insert_activity(session, activity)
    await session.commit()
    directory = generated_activity_dir(str(activity.id))
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(json.dumps(AUTHORED_MANIFEST), encoding="utf-8")
    (directory / "ui.js").write_text(AUTHORED_UI_JS, encoding="utf-8")
    (directory / "sandbox.js").write_text(AUTHORED_SANDBOX_JS, encoding="utf-8")
    return activity
