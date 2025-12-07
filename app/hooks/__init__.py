"""
Hooks system for the Sparkth plugin architecture.

This module provides Actions and Filters that allow sparkth-plugins to extend
and modify the behavior of the Sparkth application.
"""

import functools
import typing as t

# Import the core hooks API
from .actions import Action
from .contexts import Context
from .filters import Filter
from . import priorities


def clear_all(context: t.Optional[str] = None) -> None:
    """
    Clear both actions and filters for a given context.

    :param context: The context to clear. If None, clears all contexts.
    """
    Action.clear_all(context=context)
    Filter.clear_all(context=context)


def lru_cache(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
    """
    LRU cache decorator that is automatically cleared whenever sparkth-plugins are updated.

    Use this to decorate functions that need to be called multiple times with a return
    value that depends on which sparkth-plugins are loaded. Typically: functions that depend on
    the output of filters.

    This decorator is similar to `functools.lru_cache` but integrates with the plugin
    system to clear the cache when sparkth-plugins are loaded or unloaded.

    Usage::

        from app import hooks

        @hooks.lru_cache
        def get_all_routers():
            return list(hooks.Filters.API_ROUTERS.iterate())
    """
    # Import here to avoid circular dependency
    from .catalog import Actions

    decorated = functools.lru_cache(func)

    @Actions.PLUGIN_LOADED.add()
    def _clear_func_cache_on_load(_plugin: str) -> None:
        decorated.cache_clear()

    @Actions.PLUGIN_UNLOADED.add()
    def _clear_func_cache_on_unload(_plugin: str) -> None:
        decorated.cache_clear()

    return decorated


__all__ = [
    "Action",
    "Filter",
    "Context",
    "clear_all",
    "lru_cache",
    "priorities",
]
