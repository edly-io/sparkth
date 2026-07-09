import gc

import pytest

from sparkth.lib.hooks import KeyedClassHook, PluginCollectionHook, PluginHook, SingleNamedItemHook
from sparkth.lib.plugins import SparkthPlugin


def _plugin(name: str) -> SparkthPlugin:
    return SparkthPlugin(name)


class _Named:
    """Minimal item satisfying the hook's HasName bound."""

    def __init__(self, name: str) -> None:
        self.name = name


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


class _Event:
    """Minimal base for classes registered on a KeyedClassHook."""


class _LoginEvent(_Event):
    pass


class _OtherEvent(_Event):
    pass


def test_keyed_class_hook_stores_class_under_key() -> None:
    hook: KeyedClassHook[_Event] = KeyedClassHook()

    assert hook.add_class("auth.login", _LoginEvent) is True
    assert hook.get("auth.login") is _LoginEvent


def test_keyed_class_hook_readding_same_class_is_idempotent() -> None:
    hook: KeyedClassHook[_Event] = KeyedClassHook()
    hook.add_class("auth.login", _LoginEvent)

    assert hook.add_class("auth.login", _LoginEvent) is True
    assert hook.get("auth.login") is _LoginEvent


def test_keyed_class_hook_reports_collision_and_keeps_first_class() -> None:
    hook: KeyedClassHook[_Event] = KeyedClassHook()
    hook.add_class("auth.login", _LoginEvent)

    assert hook.add_class("auth.login", _OtherEvent) is False
    assert hook.get("auth.login") is _LoginEvent


def test_keyed_class_hook_get_returns_none_for_unknown_key() -> None:
    hook: KeyedClassHook[_Event] = KeyedClassHook()

    assert hook.get("missing") is None
