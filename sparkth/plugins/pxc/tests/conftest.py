"""Test environment for the PXC plugin.

``sandbox.wasm`` is a build product, kept out of git (D2), so a clean checkout has none.
``ActivityRuntime`` can be constructed without it — wasmtime is only invoked on the first
sandbox call — so only tests that actually run the sandbox carry the ``wasm`` marker, and
those skip when the binary is absent. CI builds it, so they run there. Tests that compile an
activity carry the same marker, since `make pxc.activities.build` installs the toolchain they
need along with the binary.
"""

import json
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pxc.lib.runtime import ActivityRuntime
from pxc.lib.sandbox import SandboxRuntimeError
from sqlmodel.ext.asyncio.session import AsyncSession
from uuid6 import uuid7

from sparkth.core.models.user import User
from sparkth.lib.auth import bind_current_user_id
from sparkth.main import assemble_app
from sparkth.plugins.pxc.activities import activity_dir, generated_activity_dir
from sparkth.plugins.pxc.builder import compile_sandbox
from sparkth.plugins.pxc.config import get_pxc_settings
from sparkth.plugins.pxc.event_bus import EVENT_BUS
from sparkth.plugins.pxc.models import PxcActivity
from sparkth.plugins.pxc.revisions import publish_revision
from sparkth.plugins.pxc.schemas import ActivityConfig, ActivitySource
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
    monkeypatch.setenv("PXC_REVISION_RETENTION_SECONDS", "3600")
    monkeypatch.setenv("PXC_TOOLCHAIN_DIR", str(TOOLCHAIN_DIR))
    monkeypatch.setenv("PXC_BUILD_TIMEOUT_SECONDS", "120")
    monkeypatch.setenv("PXC_BUILD_CONCURRENCY", "2")
    monkeypatch.setenv("PXC_BUILD_ERROR_LIMIT", "4000")
    monkeypatch.setenv("PXC_BUILD_STDERR_LIMIT_BYTES", "65536")
    monkeypatch.setenv("PXC_MAX_SOURCE_CHARS", "20000")
    monkeypatch.setenv("PXC_MAX_DESCRIPTION_CHARS", "2000")
    monkeypatch.setenv("PXC_LIST_ACTIVITIES_LIMIT", "20")
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


def staged_activity(question: str) -> Path:
    """A finished activity directory under the data dir's ``builds/``, as a build leaves it.

    Its one field's default is ``question``, which tells revisions apart.
    """
    staged = get_pxc_settings().data_dir / "builds" / str(uuid7())
    staged.mkdir(parents=True)
    manifest = {
        "name": "staged",
        "ui": "ui.js",
        "sandbox": "sandbox.wasm",
        "fields": {"question": {"type": "string", "scope": "activity", "default": question}},
    }
    (staged / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return staged


def question_in(directory: Path) -> str:
    """The question default of the activity files in ``directory``."""
    question: str = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))["fields"]["question"][
        "default"
    ]
    return question


async def stage_without_compiling(work: Path, manifest: dict[str, object], source: ActivitySource) -> Path:
    """Lay an activity's files down the way ``stage_activity`` does, with no compile or smoke test."""
    staged = work / "activity"
    staged.mkdir()
    (staged / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (staged / "ui.js").write_text(source.ui_js, encoding="utf-8")
    (staged / "sandbox.js").write_text(source.sandbox_js, encoding="utf-8")
    return staged


def unrunnable_activity(tmp_path: Path) -> Path:
    """The sample's manifest beside a sandbox.wasm that is not a component, so every sandbox call fails."""
    directory = tmp_path / "activity"
    directory.mkdir()
    (directory / "manifest.json").write_text((activity_dir("mcq") / "manifest.json").read_text())
    (directory / "sandbox.wasm").write_bytes(b"not a component")
    return directory


@pytest.fixture
def uncompiled_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Build and update without the toolchain: staging writes the files and skips the compile."""
    monkeypatch.setattr("sparkth.plugins.pxc.builder.stage_activity", stage_without_compiling)


# What a throwing onAction writes to stderr, and the part of it an agent is shown.
SANDBOX_STDERR = (
    "boom from onAction\nStack:\n  onAction@sandbox.js:4:30\n"
    "  export_onAction@/tmp/compile/initializer.js:387:21\n\nRedirecting call to abort() to mozalloc_abort\n"
)
THROWN_TEXT = "boom from onAction\nStack:\n  onAction@sandbox.js:4:30"


def throw_in_sandbox(runtime: ActivityRuntime, action_name: str, action_value: object) -> None:
    """Stand in for ``ActivityRuntime.on_action_or_raise`` with a sandbox whose ``onAction`` throws."""
    raise SandboxRuntimeError(
        f"Component /srv/pxc/activities/{runtime.name}/sandbox.wasm: error running 'on-action'", SANDBOX_STDERR
    )


@pytest.fixture
def throwing_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every action's sandbox throws as ``SANDBOX_STDERR`` shows, with no wasm needed."""
    monkeypatch.setattr(ActivityRuntime, "on_action_or_raise", throw_in_sandbox)


# The issue's case study: a map with runtime keys in an object field that lists no keys.
CASE_STUDY_MANIFEST: dict[str, object] = {
    "name": "placeholder",
    "ui": "ui.js",
    "sandbox": "sandbox.wasm",
    "fields": {"placements": {"type": "object", "properties": {}, "scope": "user,activity", "default": {}}},
    "actions": {
        "boom": {"type": "string"},
        "place": {"type": "object", "properties": {"animal": {"type": "string"}, "category": {"type": "string"}}},
        "logged.place": {
            "type": "object",
            "properties": {"animal": {"type": "string"}, "category": {"type": "string"}},
        },
    },
}
CASE_STUDY_SANDBOX_JS = """\
import { getField, setField } from "pxc:sandbox/state";
export function onAction(name, data, context, permission) {
  if (name === "boom") throw new Error("boom from onAction");
  const value = JSON.parse(data);
  if (name === "logged.place") console.error("placing " + value.animal);
  const placements = JSON.parse(getField("placements"));
  placements[value.animal] = value.category;
  setField("placements", JSON.stringify(placements));
  return "";
}
export function getState(context, permission) {
  return JSON.stringify({ placements: JSON.parse(getField("placements")) });
}
"""


async def compiled_activity(sandbox_js: str, manifest: dict[str, object]) -> str:
    """Compile ``sandbox_js`` and publish it with ``manifest`` as a generated activity, skipping every build check.

    Returns the new activity's id. For tests that need an activity the build would refuse.
    """
    activity_id = str(uuid7())
    staged = get_pxc_settings().data_dir / "builds" / activity_id
    staged.mkdir(parents=True)
    with tempfile.TemporaryDirectory(dir=staged.parent) as compile_dir:
        await compile_sandbox(sandbox_js, Path(compile_dir), staged / "sandbox.wasm")
    (staged / "manifest.json").write_text(json.dumps({**manifest, "name": activity_id}), encoding="utf-8")
    (staged / "ui.js").write_text(AUTHORED_UI_JS, encoding="utf-8")
    publish_revision(staged, activity_id)
    return activity_id
