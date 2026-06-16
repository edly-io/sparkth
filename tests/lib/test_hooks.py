import gc

from app.lib.hooks import PluginCollectionHook, PluginHook
from app.lib.plugins import SparkthPlugin


def _plugin(name: str) -> SparkthPlugin:
    return SparkthPlugin(name)


def test_plugin_hook_yields_added_item() -> None:
    hook: PluginHook[int] = PluginHook()
    plugin = _plugin("a")

    hook.add_item(plugin, 1)

    assert list(hook.iter_items()) == [(plugin, 1)]


def test_plugin_hook_keeps_only_last_item_per_plugin() -> None:
    hook: PluginHook[int] = PluginHook()
    plugin = _plugin("a")

    hook.add_item(plugin, 1)
    hook.add_item(plugin, 2)

    assert list(hook.iter_items()) == [(plugin, 2)]


def test_plugin_hook_iterates_sorted_by_plugin_name() -> None:
    hook: PluginHook[int] = PluginHook()
    plugin_b = _plugin("b")
    plugin_a = _plugin("a")

    hook.add_item(plugin_b, 2)
    hook.add_item(plugin_a, 1)

    assert list(hook.iter_items()) == [(plugin_a, 1), (plugin_b, 2)]


def test_collection_hook_appends_items_per_plugin() -> None:
    hook: PluginCollectionHook[int] = PluginCollectionHook()
    plugin = _plugin("a")

    hook.add_item(plugin, 1)
    hook.add_item(plugin, 2)

    assert list(hook.iter_items()) == [(plugin, 1), (plugin, 2)]


def test_collection_hook_flattens_sorted_by_plugin_name() -> None:
    hook: PluginCollectionHook[int] = PluginCollectionHook()
    plugin_b = _plugin("b")
    plugin_a = _plugin("a")

    hook.add_item(plugin_b, 3)
    hook.add_item(plugin_a, 1)
    hook.add_item(plugin_a, 2)

    assert list(hook.iter_items()) == [(plugin_a, 1), (plugin_a, 2), (plugin_b, 3)]


def test_hook_drops_items_when_plugin_is_garbage_collected() -> None:
    hook: PluginCollectionHook[int] = PluginCollectionHook()
    plugin = _plugin("a")
    hook.add_item(plugin, 1)

    del plugin
    gc.collect()

    assert list(hook.iter_items()) == []
