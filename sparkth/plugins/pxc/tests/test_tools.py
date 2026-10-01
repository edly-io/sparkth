"""Tests for the pxc MCP tools: the contract, building, listing and reading back activities."""

import json

import pytest
from pxc.lib.manifest_types import PxcActivityManifest

from sparkth.plugins.pxc import tools
from sparkth.plugins.pxc.activities import activity_dir
from sparkth.plugins.pxc.constants import PXC_ABOUT_EXAMPLE, PXC_ABOUT_FILES, PXC_ASSET_DIR, PXC_MAX_SOURCE_CHARS
from sparkth.plugins.pxc.tools import pxc_about


async def test_about_carries_the_contract_rules() -> None:
    about = (await pxc_about())["about"]

    rules = (PXC_ASSET_DIR / "about.txt").read_text(encoding="utf-8")
    assert rules.format(max_source_chars=PXC_MAX_SOURCE_CHARS) in about


async def test_about_states_the_current_source_size_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools, "PXC_MAX_SOURCE_CHARS", 12345)

    assert "12345" in (await tools.pxc_about())["about"]


async def test_about_carries_the_manifest_schema() -> None:
    about = (await pxc_about())["about"]

    assert json.dumps(PxcActivityManifest.model_json_schema(), indent=2) in about


async def test_about_carries_every_worked_example_file_as_it_is_on_disk() -> None:
    about = (await pxc_about())["about"]

    for name in PXC_ABOUT_FILES:
        assert (activity_dir(PXC_ABOUT_EXAMPLE) / name).read_text(encoding="utf-8") in about
