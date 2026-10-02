import gc
import logging
from collections.abc import Iterator

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from sparkth.core.models.plugin import Plugin
from sparkth.lib.chat.hooks import CHAT_RESPONSIBILITIES, ChatResponsibility, enabled_responsibilities
from sparkth.lib.plugins import SparkthPlugin

STUB = ChatResponsibility("stub-job", "Stub scope.", "Stub prompt {current_datetime}", frozenset({"stub"}))


@pytest.fixture
def stub_plugin() -> Iterator[SparkthPlugin]:
    """A plugin registering STUB; its weakly-keyed entry goes when the plugin is collected."""
    plugin = SparkthPlugin("stub")
    CHAT_RESPONSIBILITIES.add_item(plugin, STUB)
    yield plugin
    del plugin
    gc.collect()


async def test_a_registered_job_is_enabled_by_name(session: AsyncSession, stub_plugin: SparkthPlugin) -> None:
    assert (await enabled_responsibilities(session))["stub-job"] == STUB


async def test_a_job_of_a_plugin_disabled_system_wide_is_left_out(
    session: AsyncSession, stub_plugin: SparkthPlugin
) -> None:
    session.add(Plugin(name="stub", enabled=False))
    await session.commit()

    assert "stub-job" not in await enabled_responsibilities(session)


async def test_a_plugin_constructed_twice_is_not_a_collision(
    session: AsyncSession, stub_plugin: SparkthPlugin, caplog: pytest.LogCaptureFixture
) -> None:
    """The loader and tests both construct plugins, so the same job arrives from two instances."""
    second = SparkthPlugin("stub")
    CHAT_RESPONSIBILITIES.add_item(second, STUB)

    with caplog.at_level(logging.ERROR, logger="sparkth.lib.chat.hooks"):
        jobs = await enabled_responsibilities(session)

    assert jobs["stub-job"] == STUB
    assert caplog.text == ""


async def test_a_second_plugin_claiming_the_name_is_ignored_and_logged(
    session: AsyncSession, stub_plugin: SparkthPlugin, caplog: pytest.LogCaptureFixture
) -> None:
    """Conversations store the name, so two jobs under one name would route each other's."""
    rival = SparkthPlugin("zz-rival")
    CHAT_RESPONSIBILITIES.add_item(rival, ChatResponsibility("stub-job", "Other.", "Other", frozenset()))

    with caplog.at_level(logging.ERROR, logger="sparkth.lib.chat.hooks"):
        jobs = await enabled_responsibilities(session)

    assert jobs["stub-job"] == STUB
    assert "zz-rival" in caplog.text
