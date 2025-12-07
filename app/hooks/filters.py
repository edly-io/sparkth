from __future__ import annotations

"""
Filter hooks for transforming data.

Filters are used to modify data at specific points during the application
lifecycle. Unlike actions, filters transform data by passing it through
a chain of callbacks.
"""

import sys
import typing as t
from weakref import WeakSet

from typing_extensions import Concatenate, ParamSpec

from . import contexts, priorities

#: Filter generic return value, which is also the type of the first callback argument.
T1 = t.TypeVar("T1")
#: Filter generic signature for all arguments after the first one.
T2 = ParamSpec("T2")
#: Specialized typevar for list elements
L = t.TypeVar("L")

FilterCallbackFunc = t.Callable[Concatenate[T1, T2], T1]


class FilterCallback(contexts.Contextualized, t.Generic[T1, T2]):
    """
    A callback function associated with a filter.

    This class wraps a callback function and tracks its priority and context.
    """

    def __init__(
        self,
        func: FilterCallbackFunc[T1, T2],
        priority: t.Optional[int] = None,
    ):
        """
        Initialize a filter callback.

        :param func: The callback function to execute
        :param priority: Optional priority (default: priorities.DEFAULT)
        """
        super().__init__()
        self.func = func
        self.priority = priority or priorities.DEFAULT

    def apply(self, value: T1, *args: T2.args, **kwargs: T2.kwargs) -> T1:
        """
        Apply the callback function to transform a value.

        :param value: The value to transform
        :param args: Additional positional arguments
        :param kwargs: Additional keyword arguments
        :return: The transformed value
        """
        return self.func(value, *args, **kwargs)


class Filter(t.Generic[T1, T2]):
    """
    Filter hooks have callbacks that are triggered as a chain.

    Several filters are defined across the codebase. Each filter is given a unique
    name. To each filter are associated zero or more callbacks, sorted by priority.

    This is the typical filter lifecycle:

    1. Create a filter with ``Filter()``.
    2. Add callbacks with :py:meth:`add`.
    3. Call the filter callbacks with method :py:meth:`apply`.

    The result of each callback is passed as the first argument to the next one. Thus,
    the type of the first argument must match the callback return type.

    The ``T1`` and ``T2`` type parameters of the Filter class correspond to the expected
    signature of the filter callbacks. ``T1`` is the type of the first argument (and thus
    the return value type as well) and ``T2`` is the signature of the other arguments.

    For instance, `Filter[str, [int]]` means that the filter callbacks are expected to
    take two arguments: one string and one integer. Each callback must then return a
    string.

    This strong typing makes it easier for plugin developers to quickly check whether
    they are adding and calling filter callbacks correctly.

    Usage::

        from app import hooks

        # Define a filter
        MY_FILTER = hooks.Filter[list[str], []]()

        # Add a callback
        @MY_FILTER.add()
        def add_item(items: list[str]) -> list[str]:
            items.append("new_item")
            return items

        # Apply the filter
        result = MY_FILTER.apply([])  # Returns ["new_item"]
    """

    # Keep a weak reference to all created filters. This allows us to clear them when
    # necessary.
    INSTANCES: WeakSet[Filter[t.Any, t.Any]] = WeakSet()

    def __init__(self) -> None:
        """
        Initialize a filter with an empty callback list.
        """
        self.callbacks: list[FilterCallback[T1, T2]] = []
        self.INSTANCES.add(self)

    def add(
        self, priority: t.Optional[int] = None
    ) -> t.Callable[[FilterCallbackFunc[T1, T2]], FilterCallbackFunc[T1, T2]]:
        """
        Decorator to add a filter callback.

        Callbacks are added by increasing priority. Highest priority scores are called
        last.

        :param priority: optional order in which the filter callbacks are called. Higher
          values mean that they will be performed later. The default value is
          ``priorities.DEFAULT`` (10). Filters that must be called last should have a
          priority of 100.

        The return value of each filter function callback will be passed as the first argument to the next one.

        Usage::

            from app import hooks

            @hooks.Filters.MY_FILTER.add()
            def my_func(value, some_other_arg):
                # Do something with `value`
                ...
                return value

        After filters have been created, the result of calling all filter callbacks is obtained by running::

            final_value = hooks.Filters.MY_FILTER.apply(initial_value, some_other_argument_value)
        """

        def inner(func: FilterCallbackFunc[T1, T2]) -> FilterCallbackFunc[T1, T2]:
            callback: FilterCallback[T1, T2] = FilterCallback(func, priority=priority)
            priorities.insert_callback(callback, self.callbacks)
            return func

        return inner

    def apply(
        self,
        value: T1,
        *args: T2.args,
        **kwargs: T2.kwargs,
    ) -> T1:
        """
        Apply all declared filters to a single value, passing along the additional arguments.

        The return value of every filter is passed as the first argument to the next callback.

        Usage::

            from app import hooks

            results = hooks.Filters.MY_FILTER.apply(["item0"])

        :param value: The initial value to transform
        :return: The transformed value after all callbacks have been applied
        """
        return self.apply_from_context(None, value, *args, **kwargs)

    def apply_from_context(
        self,
        context: t.Optional[str],
        value: T1,
        *args: T2.args,
        **kwargs: T2.kwargs,
    ) -> T1:
        """
        Same as :py:meth:`apply` but only run the callbacks that were created in a given context.

        If ``context`` is None then it is ignored.

        :param context: Context name to filter callbacks by
        :param value: The initial value to transform
        :return: The transformed value
        """
        for callback in self.callbacks:
            if callback.is_in_context(context):
                try:
                    value = callback.apply(
                        value,
                        *args,
                        **kwargs,
                    )
                except:
                    sys.stderr.write(
                        f"Error applying filter: func={callback.func} contexts={callback.contexts}\n"
                    )
                    raise
        return value

    def clear(self, context: t.Optional[str] = None) -> None:
        """
        Clear any previously defined filter with the given context.

        :param context: Context name to clear callbacks from
        """
        self.callbacks = [
            callback
            for callback in self.callbacks
            if not callback.is_in_context(context)
        ]

    @classmethod
    def clear_all(cls, context: t.Optional[str] = None) -> None:
        """
        Clear any previously defined filter with the given context.

        :param context: Context name to clear callbacks from
        """
        for filtre in cls.INSTANCES:
            filtre.clear(context)

    # The methods below are specific to filters which take lists as first arguments
    def add_item(
        self: "Filter[list[L], T2]", item: L, priority: t.Optional[int] = None
    ) -> None:
        """
        Convenience decorator to add a single item to a filter that returns a list of items.

        This method is only valid for filters that return list of items.

        :param item: item that will be appended to the resulting list.
        :param priority: see :py:data:`Filter.add`.

        Usage::

            from app import hooks

            hooks.Filters.MY_LIST_FILTER.add_item("item1")
            hooks.Filters.MY_LIST_FILTER.add_item("item2")

            assert ["item1", "item2"] == hooks.Filters.MY_LIST_FILTER.apply([])
        """
        self.add_items([item], priority=priority)

    def add_items(
        self: "Filter[list[L], T2]", items: list[L], priority: t.Optional[int] = None
    ) -> None:
        """
        Convenience function to add multiple items to a filter that returns a list of items.

        This method is only valid for filters that return list of items.

        This is a similar method to :py:data:`Filter.add_item` except that it can be
        used to add multiple items at the same time. If you find yourself calling
        ``add_item`` multiple times on the same filter, you should probably use a
        single call to ``add_items`` instead.

        :param items: items that will be appended to the resulting list.
        :param priority: optional priority.

        Usage::

            from app import hooks

            hooks.Filters.MY_LIST_FILTER.add_items(["item1", "item2"])
            hooks.Filters.MY_LIST_FILTER.add_items(["item3", "item4"])

            assert ["item1", "item2", "item3", "item4"] == hooks.Filters.MY_LIST_FILTER.apply([])

        The following are equivalent::

            # Single call to add_items
            hooks.Filters.MY_LIST_FILTER.add_items(["item1", "item2"])

            # Multiple calls to add_item
            hooks.Filters.MY_LIST_FILTER.add_item("item1")
            hooks.Filters.MY_LIST_FILTER.add_item("item2")
        """

        @self.add(priority=priority)
        def callback(
            values: list[L], /, *_args: T2.args, **_kwargs: T2.kwargs
        ) -> list[L]:
            return values + items

    def iterate(
        self: "Filter[list[L], T2]", *args: T2.args, **kwargs: T2.kwargs
    ) -> t.Iterator[L]:
        """
        Convenient function to iterate over the results of a filter result list.

        This method is only valid for filters that return list of items.

        These pieces of code are equivalent::

            for value in hooks.Filters.MY_LIST_FILTER.apply([], *args, **kwargs):
                ...

            for value in hooks.Filters.MY_LIST_FILTER.iterate(*args, **kwargs):
                ...

        :return: iterator over the list of items from the filter
        """
        yield from self.iterate_from_context(None, *args, **kwargs)

    def iterate_from_context(
        self: "Filter[list[L], T2]",
        context: t.Optional[str],
        *args: T2.args,
        **kwargs: T2.kwargs,
    ) -> t.Iterator[L]:
        """
        Same as :py:func:`Filter.iterate` but apply only callbacks from a given context.

        :param context: Context name to filter callbacks by
        :return: iterator over the list of items from the filter
        """
        yield from self.apply_from_context(context, [], *args, **kwargs)
