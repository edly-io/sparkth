from __future__ import annotations
"""
Action hooks for triggering callbacks.

Actions are used to trigger callback functions at specific moments in the
application lifecycle. Unlike filters, actions do not transform data -
they simply execute callbacks in sequence.
"""

import sys
import typing as t
from weakref import WeakSet

from typing_extensions import ParamSpec

from . import priorities
from .contexts import Contextualized

#: Action generic signature.
T = ParamSpec("T")

ActionCallbackFunc = t.Callable[T, None]


class ActionCallback(Contextualized, t.Generic[T]):
    """
    A callback function associated with an action.

    This class wraps a callback function and tracks its priority and context.
    """

    def __init__(
        self,
        func: ActionCallbackFunc[T],
        priority: t.Optional[int] = None,
    ):
        """
        Initialize an action callback.

        :param func: The callback function to execute
        :param priority: Optional priority (default: priorities.DEFAULT)
        """
        super().__init__()
        self.func = func
        self.priority = priority or priorities.DEFAULT

    def do(
        self,
        *args: T.args,
        **kwargs: T.kwargs,
    ) -> None:
        """
        Execute the callback function.

        :param args: Positional arguments to pass to the callback
        :param kwargs: Keyword arguments to pass to the callback
        """
        self.func(*args, **kwargs)


class Action(t.Generic[T]):
    """
    Action hooks have callbacks that are triggered independently from one another.

    Several actions are defined across the codebase. Each action is given a unique name.
    To each action are associated zero or more callbacks, sorted by priority.

    This is the typical action lifecycle:

    1. Create an action with ``Action()``.
    2. Add callbacks with :py:meth:`add`.
    3. Call the action callbacks with :py:meth:`do`.

    The ``T`` type parameter of the Action class corresponds to the expected signature of
    the action callbacks. For instance, ``Action[[str, int]]`` means that the action
    callbacks are expected to take two arguments: one string and one integer.

    This strong typing makes it easier for plugin developers to quickly check whether
    they are adding and calling action callbacks correctly.

    Usage::

        from app import hooks

        # Define an action
        MY_ACTION = hooks.Action[[str, int]]()

        # Add a callback
        @MY_ACTION.add()
        def my_callback(name: str, count: int):
            print(f"Hello {name}, count is {count}")

        # Trigger the action
        MY_ACTION.do("World", 42)
    """

    # Keep a weak reference to all created actions. This allows us to clear them when
    # necessary.
    INSTANCES: WeakSet[Action[t.Any]] = WeakSet()

    def __init__(self) -> None:
        """
        Initialize an action with an empty callback list.
        """
        self.callbacks: list[ActionCallback[T]] = []
        self.INSTANCES.add(self)

    def add(
        self, priority: t.Optional[int] = None
    ) -> t.Callable[[ActionCallbackFunc[T]], ActionCallbackFunc[T]]:
        """
        Decorator to add a callback to an action.

        :param priority: optional order in which the action callbacks are performed. Higher
            values mean that they will be performed later. The default value is
            ``priorities.DEFAULT`` (10). Actions that should be performed last should have a
            priority of 100.

        Usage::

            from app import hooks

            @hooks.Actions.MY_ACTION.add()
            def do_stuff(my_arg):
                # Do stuff here
                ...

        The ``do_stuff`` callback function will be called on ``hooks.Actions.MY_ACTION.do(some_arg)``.

        The signature of each callback action function must match the signature of the
        corresponding :py:meth:`do` method. Callback action functions are not supposed
        to return any value. Returned values will be ignored.
        """

        def inner(func: ActionCallbackFunc[T]) -> ActionCallbackFunc[T]:
            callback = ActionCallback(func, priority=priority)
            priorities.insert_callback(callback, self.callbacks)
            return func

        return inner

    def do(
        self,
        *args: T.args,
        **kwargs: T.kwargs,
    ) -> None:
        """
        Run the action callbacks in sequence.

        Extra ``*args`` and ``*kwargs`` arguments will be passed as-is to
        callback functions.

        Callbacks are executed in order of priority, then FIFO. There is no error
        management here: a single exception will cause all following callbacks
        not to be run and the exception will be bubbled up.

        Usage::

            from app import hooks

            hooks.Actions.MY_ACTION.do("argument1", "argument2")
        """
        self.do_from_context(None, *args, **kwargs)

    def do_from_context(
        self,
        context: t.Optional[str],
        *args: T.args,
        **kwargs: T.kwargs,
    ) -> None:
        """
        Same as :py:meth:`do` but only run the callbacks from a given context.

        :param context: limit the set of callback actions to those that
            were declared within a certain context (see
            :py:func:`app.hooks.contexts.enter`).

        Usage::

            from app import hooks

            hooks.Actions.MY_ACTION.do_from_context("plugin:myplugin", "arg1", "arg2")
        """
        for callback in self.callbacks:
            if callback.is_in_context(context):
                try:
                    callback.do(
                        *args,
                        **kwargs,
                    )
                except:
                    sys.stderr.write(
                        f"Error applying action: func={callback.func} contexts={callback.contexts}\n"
                    )
                    raise

    def clear(self, context: t.Optional[str] = None) -> None:
        """
        Clear all or part of the callbacks associated to an action.

        :param context: when defined, will clear only the actions that were
            created within that context.

        Actions will be removed from the list of callbacks and will no longer be
        run in :py:meth:`do` calls.

        This function should almost certainly never be called by sparkth-plugins. It is
        mostly useful to disable some sparkth-plugins at runtime or in unit tests.
        """
        self.callbacks = [
            callback
            for callback in self.callbacks
            if not callback.is_in_context(context)
        ]

    @classmethod
    def clear_all(cls, context: t.Optional[str] = None) -> None:
        """
        Clear any previously defined action with the given context.

        :param context: when defined, will clear only the actions that were
            created within that context.
        """
        for action in cls.INSTANCES:
            action.clear(context)
