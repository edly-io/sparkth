import gc
from collections.abc import Iterator
from typing import Any

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.lib.config.hooks import CONFIG_ADAPTERS
from sparkth.lib.plugins import ConfigAdapter, PluginService, SparkthPlugin


class _RecordingAdapter(ConfigAdapter):
    """Overrides only sync_cache, recording each call."""

    def __init__(self) -> None:
        self.calls: list[tuple[int, dict[str, Any]]] = []

    async def sync_cache(self, *, session: AsyncSession, user_id: int, stored_config: dict[str, Any]) -> None:
        self.calls.append((user_id, stored_config))


@pytest.fixture
def adapter() -> Iterator[_RecordingAdapter]:
    """Register the adapter under a throwaway plugin; the hook holds the plugin weakly."""
    recording = _RecordingAdapter()
    owner = SparkthPlugin("sample")
    CONFIG_ADAPTERS.add_item(owner, recording)
    yield recording
    del owner
    gc.collect()


async def test_an_adapter_overriding_only_sync_cache_keeps_config_unchanged(
    session: AsyncSession, adapter: _RecordingAdapter
) -> None:
    assert await PluginService.apply_preprocess("sample", session, 1, {"a": 1}) == {"a": 1}
    assert await PluginService.apply_postprocess("sample", session, 1, {"a": 1}) == {"a": 1}
    await PluginService.apply_cache_sync("sample", session, 1, {"a": 1})
    assert adapter.calls == [(1, {"a": 1})]
