from __future__ import annotations
"""
Context management for plugin isolation.

Contexts allow sparkth-plugins to be loaded and unloaded cleanly by tracking which
callbacks belong to which plugin.
"""

import typing as t
from contextlib import contextmanager


class Context:
    """
    A context represents a scope in which hooks are created.

    When hooks are created within a context, they are tagged with that context's name.
    This allows us to selectively clear or run hooks from specific contexts.
    """

    #: Stack of currently active contexts
    STACK: list[Context] = []

    def __init__(self, name: str):
        """
        Initialize a context with a unique name.

        :param name: A unique identifier for this context
        """
        self.name = name

    def enter(self) -> "ContextManager":
        """
        Enter this context.

        Returns a context manager that can be used with the 'with' statement.

        Usage::

            with my_context.enter():
                # All hooks created here will be tagged with this context
                @my_action.add()
                def my_callback():
                    pass
        """
        return ContextManager(self)

    def __str__(self) -> str:
        """Return the context name."""
        return self.name


class ContextManager:
    """
    Context manager for entering and exiting contexts.

    This is used internally by Context.enter() and should not be instantiated directly.
    """

    def __init__(self, context: Context):
        """
        Initialize the context manager.

        :param context: The context to manage
        """
        self.context = context

    def __enter__(self) -> Context:
        """
        Enter the context by pushing it onto the stack.

        :return: The context that was entered
        """
        Context.STACK.append(self.context)
        return self.context

    def __exit__(self, exc_type: t.Any, exc_val: t.Any, exc_tb: t.Any) -> None:
        """
        Exit the context by popping it from the stack.
        """
        Context.STACK.pop()


class Contextualized:
    """
    Base class for objects that can be associated with contexts.

    This class tracks which contexts an object was created in, allowing
    for selective filtering and clearing of objects by context.
    """

    def __init__(self) -> None:
        """
        Initialize contextualized object.

        Records the current context stack at the time of creation.
        """
        #: List of context names this object belongs to
        self.contexts: list[str] = [c.name for c in Context.STACK]

    def is_in_context(self, context: t.Optional[str]) -> bool:
        """
        Check if this object belongs to a specific context.

        :param context: The context name to check, or None to match all contexts
        :return: True if the object belongs to the context, False otherwise
        """
        if context is None:
            return True
        return context in self.contexts
