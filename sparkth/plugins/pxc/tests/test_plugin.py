from sparkth.lib.chat.hooks import CHAT_RESPONSIBILITIES
from sparkth.lib.frontend.hooks import DISPLAY_INFO
from sparkth.lib.mcp.hooks import MCP_TOOLS
from sparkth.lib.plugins import get_plugin_loader
from sparkth.plugins.pxc.plugin import PXC_ACTIVITY, PxcPlugin


def test_the_plugin_is_named_pxc() -> None:
    assert PxcPlugin().name == "pxc"


def test_the_plugin_declares_display_info() -> None:
    plugin = PxcPlugin()

    assert any(item.display_name for owner, item in DISPLAY_INFO.iter_items() if owner is plugin)


def test_the_plugin_is_actually_loaded_by_the_loader() -> None:
    # Not a formality. PluginLoader._load_all wraps construction in a broad `except Exception`
    # and only logs, so a plugin that fails to import is silently absent — and a plugin missing
    # from the PLUGINS list is absent with no log at all. Either way every route it serves 404s
    # and nothing else fails. This is the test that names the cause.
    loaded_names = [name for name, _ in get_plugin_loader().get_loaded_plugins()]
    assert "pxc" in loaded_names


def test_the_plugin_contributes_its_tools_under_the_pxc_category() -> None:
    plugin = PxcPlugin()

    tools = {tool.name: tool.category for owner, tool in MCP_TOOLS.iter_items() if owner is plugin}

    assert tools == {
        "pxc_about": "pxc",
        "pxc_build_activity": "pxc",
        "pxc_list_activities": "pxc",
        "pxc_get_activity_source": "pxc",
    }


def test_the_plugin_registers_the_activity_job() -> None:
    plugin = PxcPlugin()

    jobs = [job for owner, job in CHAT_RESPONSIBILITIES.iter_items() if owner is plugin]

    assert jobs == [PXC_ACTIVITY]


def test_the_activity_job_claims_the_pxc_tools() -> None:
    assert PXC_ACTIVITY.name == "pxc-activity"
    assert PXC_ACTIVITY.tool_categories == frozenset({"pxc"})


def test_the_activity_system_prompt_renders_with_the_refusal_sentence() -> None:
    # Chat renders it with str.format, so a stray brace in the asset would raise here.
    rendered = PXC_ACTIVITY.system_prompt.format(current_datetime="2026-10-01", refusal_message="REFUSAL")

    assert "REFUSAL" in rendered
