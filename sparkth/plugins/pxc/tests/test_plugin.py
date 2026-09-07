from sparkth.lib.frontend.hooks import DISPLAY_INFO
from sparkth.lib.plugins import get_plugin_loader
from sparkth.plugins.pxc.plugin import PxcPlugin


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
