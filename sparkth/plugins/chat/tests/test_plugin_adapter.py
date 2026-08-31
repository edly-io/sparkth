"""The chat plugin's LLM-config adapter is registered and reached.

The adapter is what validates that a chat config's llm_config_id belongs to the user asking,
so losing its registration would quietly let one user point their chat config at another user's
LLM key. What the adapter itself does is covered centrally in tests/llm/test_plugin_adapter.py;
what is asserted here is that the config pipeline reaches it for this plugin.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sparkth.lib.plugins import PluginService


def _session_finding_nothing() -> AsyncMock:
    """A session whose LLMConfig lookup comes back empty — the not-yours case."""
    session = AsyncMock()
    result = MagicMock()
    result.first.return_value = None
    session.exec.return_value = result
    return session


@pytest.mark.asyncio
async def test_the_config_pipeline_rejects_a_config_the_user_does_not_own() -> None:
    """Proves the registration is reached, not merely present: PluginService looks the adapter
    up by plugin name, and an unowned llm_config_id must not survive the round trip."""
    with pytest.raises(ValueError, match="llm_config_id"):
        await PluginService.apply_preprocess("chat", _session_finding_nothing(), 1, {"llm_config_id": 999})
