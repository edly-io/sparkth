import weakref
from typing import Generic, Iterator, TypeVar

from app.plugins.base import SparkthPlugin

T = TypeVar("T")


class BasePluginHook(Generic[T]):
    def __init__(self) -> None:
        self._items: weakref.WeakKeyDictionary[SparkthPlugin, T] = weakref.WeakKeyDictionary()

    def _iter_plugin_items(self) -> Iterator[tuple[SparkthPlugin, T]]:
        items = list(self._items.items())

        # Sort items by alphabetical plugin name
        items.sort(key=lambda item: item[0].name)

        yield from items


class PluginHook(BasePluginHook[T]):
    """A hook that holds a single item per plugin (the last one added wins)."""

    def add_item(self, plugin: SparkthPlugin, item: T) -> None:
        self._items[plugin] = item

    def iter_items(self) -> Iterator[tuple[SparkthPlugin, T]]:
        yield from self._iter_plugin_items()


class PluginCollectionHook(BasePluginHook[list[T]]):
    """A hook that holds a list of items per plugin."""

    def add_item(self, plugin: SparkthPlugin, item: T) -> None:
        self.add_items(plugin, [item])

    def add_items(self, plugin: SparkthPlugin, items: list[T]) -> None:
        if plugin not in self._items:
            self._items[plugin] = []
        self._items[plugin].extend(items)

    def iter_items(self) -> Iterator[tuple[SparkthPlugin, T]]:
        for plugin, plugin_items in self._iter_plugin_items():
            for plugin_item in plugin_items:
                yield plugin, plugin_item
