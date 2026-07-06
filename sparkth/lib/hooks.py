import weakref
from typing import Callable, Generic, Iterator, Protocol, TypeVar

from sparkth.lib.plugins import SparkthPlugin


class HasName(Protocol):
    # Structural bound for SingleNamedItemHook's type var, so the generic hook can read
    # ``item.name`` under mypy --strict. Any object with a ``name: str`` satisfies it.
    name: str


N = TypeVar("N", bound=HasName)
T = TypeVar("T")
K = TypeVar("K")


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


class KeyedClassHook(Generic[T]):
    """A flat hook holding classes keyed by an explicit string.

    Unlike :class:`SingleNamedItemHook` (instances keyed by their ``name``),
    this hook stores *classes* under a caller-derived key, and re-adding the
    same class under its key is a no-op so module re-imports stay idempotent.
    Only a *different* class claiming an occupied key is a collision, reported
    by ``add_class`` returning ``False`` so domain hooks can raise their own
    exception type.
    """

    def __init__(self) -> None:
        self._classes: dict[str, type[T]] = {}

    def add_class(self, key: str, item_cls: type[T]) -> bool:
        """Store ``item_cls`` under ``key``.

        Returns ``True`` if stored (or already stored), ``False`` when a
        different class already claims ``key`` (the stored class is kept).
        """
        existing = self._classes.get(key)
        if existing is not None and existing is not item_cls:
            return False
        self._classes[key] = item_cls
        return True

    def get(self, key: str) -> type[T] | None:
        """Return the class stored under ``key``, or ``None`` if the key is free."""
        return self._classes.get(key)


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


class KeyedItemHook(Generic[K, T]):
    """A flat hook keyed by a caller-supplied key function.

    Generalizes :class:`SingleNamedItemHook` (which keys by ``item.name``) to any
    hashable key — e.g. a composite ``(event_type, version)``. Adding a second item
    whose key is already present raises ``ValueError``. Callers that want a domain-specific error
    validate before / translate around ``add_item`` (as the analytics factory does).
    """

    def __init__(self, key: Callable[[T], K]) -> None:
        self._key = key
        self._items: dict[K, T] = {}

    def add_item(self, item: T) -> None:
        key = self._key(item)
        if key in self._items:
            raise ValueError(f"Duplicate hook item for key {key!r}")
        self._items[key] = item

    def get(self, key: K) -> T | None:
        """Return the item registered under ``key``, or ``None`` if none is registered."""
        return self._items.get(key)

    def remove(self, key: K) -> None:
        """Remove the item registered under ``key`` if present; a no-op otherwise.

        Lets callers undo a registration (e.g. test cleanup) without reaching into
        the hook's internal storage.
        """
        self._items.pop(key, None)
