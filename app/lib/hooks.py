import weakref
from typing import Generic, Iterator, Protocol, TypeVar

from app.lib.plugins import SparkthPlugin


class HasName(Protocol):
    # Structural bound for SingleNamedItemHook's type var, so the generic hook can read
    # ``item.name`` under mypy --strict. Any object with a ``name: str`` satisfies it.
    name: str


N = TypeVar("N", bound=HasName)
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


class SingleNamedItemHook(Generic[N]):
    """A flat hook holding items identified by a unique ``name``.

    Each item is added directly and keyed by its ``name``. Adding a second item whose
    name is already present raises ``ValueError``.
    """

    def __init__(self) -> None:
        self._items: dict[str, N] = {}

    def add_item(self, item: N) -> None:
        if item.name in self._items:
            raise ValueError(f"Duplicate hook item: {item.name}")
        self._items[item.name] = item

    def iter_values(self) -> Iterator[N]:
        yield from self._items.values()

    def iter_items(self) -> Iterator[tuple[str, N]]:
        yield from self._items.items()

    def get(self, name: str, default: N | None = None) -> N | None:
        """Return the item registered under ``name``, or ``default`` if none is registered."""
        return self._items.get(name, default)
