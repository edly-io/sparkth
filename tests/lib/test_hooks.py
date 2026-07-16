import gc

import pytest

from sparkth.lib.hooks import (
    KeyedItemHook,
    PluginCollectionHook,
    PluginHook,
    SingleNamedItemHook,
)
from sparkth.lib.plugins import SparkthPlugin


def _plugin(name: str) -> SparkthPlugin:
    return SparkthPlugin(name)


class _Named:
    """Minimal item satisfying the hook's HasName bound."""

    def __init__(self, name: str) -> None:
        self.name = name


class _Keyed:
    """Minimal item for KeyedItemHook, keyed by a composite ``(kind, version)``."""

    def __init__(self, kind: str, version: int) -> None:
        self.kind = kind
        self.version = version


def _keyed_hook() -> KeyedItemHook[tuple[str, int], _Keyed]:
    return KeyedItemHook(key=lambda item: (item.kind, item.version))


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


def test_single_named_item_hook_yields_added_items() -> None:
    hook: SingleNamedItemHook[_Named] = SingleNamedItemHook()
    first = _Named("a")
    second = _Named("b")

    hook.add_item(first)
    hook.add_item(second)

    assert list(hook.iter_values()) == [first, second]


def test_single_named_item_hook_iter_items_yields_name_value_pairs() -> None:
    hook: SingleNamedItemHook[_Named] = SingleNamedItemHook()
    first = _Named("a")
    second = _Named("b")

    hook.add_item(first)
    hook.add_item(second)

    assert list(hook.iter_items()) == [("a", first), ("b", second)]


def test_single_named_item_hook_preserves_insertion_order() -> None:
    # Insertion order (not alphabetic) so hierarchical items reach consumers
    # parent-before-child — here "course" must precede its child "course.module".
    hook: SingleNamedItemHook[_Named] = SingleNamedItemHook()
    parent = _Named("course")
    child = _Named("course.module")

    hook.add_item(parent)
    hook.add_item(child)

    assert list(hook.iter_values()) == [parent, child]


def test_single_named_item_hook_rejects_duplicate_name() -> None:
    hook: SingleNamedItemHook[_Named] = SingleNamedItemHook()
    hook.add_item(_Named("course.grade"))

    with pytest.raises(ValueError, match="course.grade"):
        hook.add_item(_Named("course.grade"))


def test_single_named_item_hook_get_returns_item_by_name() -> None:
    hook: SingleNamedItemHook[_Named] = SingleNamedItemHook()
    item = _Named("a")
    hook.add_item(item)

    assert hook.get("a") is item


def test_single_named_item_hook_get_returns_none_for_unknown_name() -> None:
    hook: SingleNamedItemHook[_Named] = SingleNamedItemHook()

    assert hook.get("missing") is None


def test_single_named_item_hook_get_returns_default_for_unknown_name() -> None:
    hook: SingleNamedItemHook[_Named] = SingleNamedItemHook()
    fallback = _Named("fallback")

    assert hook.get("missing", fallback) is fallback


def test_keyed_item_hook_get_returns_added_item() -> None:
    hook = _keyed_hook()
    item = _Keyed("thing_happened", 1)
    hook.add_item(item)

    assert hook.get(("thing_happened", 1)) is item


def test_keyed_item_hook_rejects_duplicate_key() -> None:
    hook = _keyed_hook()
    hook.add_item(_Keyed("thing_happened", 1))

    with pytest.raises(ValueError):
        hook.add_item(_Keyed("thing_happened", 1))


def test_keyed_item_hook_get_returns_none_for_unknown_key() -> None:
    hook = _keyed_hook()

    assert hook.get(("missing", 1)) is None


def test_keyed_item_hook_remove_deletes_item() -> None:
    hook = _keyed_hook()
    hook.add_item(_Keyed("thing_happened", 1))

    hook.remove(("thing_happened", 1))

    assert hook.get(("thing_happened", 1)) is None
    # Removal frees the key, so the same key can be registered again.
    hook.add_item(_Keyed("thing_happened", 1))


def test_keyed_item_hook_remove_is_noop_for_unknown_key() -> None:
    hook = _keyed_hook()

    # No KeyError for a key that was never registered.
    hook.remove(("missing", 1))


def test_keyed_item_hook_iter_values_yields_added_items_in_insertion_order() -> None:
    hook = _keyed_hook()
    first = _Keyed("a", 1)
    second = _Keyed("b", 1)
    hook.add_item(first)
    hook.add_item(second)

    assert list(hook.iter_values()) == [first, second]


def test_keyed_item_hook_iter_values_is_empty_when_unused() -> None:
    hook = _keyed_hook()

    assert list(hook.iter_values()) == []
