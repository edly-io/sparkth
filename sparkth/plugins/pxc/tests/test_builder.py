"""The activity build: manifest rules, bounded child processes, compile, smoke test, storage."""

import json

import pytest
from pydantic import ValidationError

from sparkth.plugins.pxc.activities import activity_dir
from sparkth.plugins.pxc.builder import validate_manifest
from sparkth.plugins.pxc.constants import PXC_MAX_SOURCE_CHARS
from sparkth.plugins.pxc.exceptions import PxcManifestInvalid
from sparkth.plugins.pxc.schemas import ActivitySource

OWNER = 1
MCQ = activity_dir("mcq")
MCQ_MANIFEST: dict[str, object] = json.loads((MCQ / "manifest.json").read_text())


def test_the_manifest_is_named_after_the_activity_id() -> None:
    assert validate_manifest({**MCQ_MANIFEST, "name": "anything"}, "the-id")["name"] == "the-id"


def test_a_manifest_outside_the_pxc_schema_names_the_field_at_fault() -> None:
    without_ui = {key: value for key, value in MCQ_MANIFEST.items() if key != "ui"}

    with pytest.raises(PxcManifestInvalid) as refused:
        validate_manifest(without_ui, "the-id")

    assert "ui: Field required" in str(refused.value)


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"assets": ["picture.png"]}, "assets"),
        ({"capabilities": {"grading": {}}}, "capabilities"),
        ({"ui": "main.js"}, "ui"),
        ({"sandbox": "other.wasm"}, "sandbox"),
    ],
)
def test_a_manifest_breaking_a_build_rule_is_refused(change: dict[str, object], field: str) -> None:
    with pytest.raises(PxcManifestInvalid) as refused:
        validate_manifest({**MCQ_MANIFEST, **change}, "the-id")

    assert f'"{field}"' in str(refused.value)


@pytest.mark.parametrize("field", ["ui_js", "sandbox_js"])
def test_source_over_the_size_limit_is_refused_before_any_build(field: str) -> None:
    sources = {"ui_js": "", "sandbox_js": "", field: "x" * (PXC_MAX_SOURCE_CHARS + 1)}

    with pytest.raises(ValidationError):
        ActivitySource.model_validate({"title": "t", "description": "d", "manifest": {}, **sources})
