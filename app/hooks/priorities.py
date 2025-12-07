
"""
Priority levels for action and filter callbacks.

Higher priority callbacks are executed later. The default priority is 10.
"""

# Plugins that should run very early
HIGHEST = 0

# Plugins that should run early
HIGH = 5

# Default priority for most sparkth-plugins
DEFAULT = 10

# Plugins that should run late
LOW = 15

# Plugins that should run very late
LOWEST = 20


def insert_callback(callback, callbacks):
    """
    Insert a callback into a list of callbacks, sorted by priority.

    Callbacks with lower priority values are executed first.
    If two callbacks have the same priority, they are executed in FIFO order.

    :param callback: The callback to insert
    :param callbacks: The list of callbacks to insert into
    """
    # Find the insertion point based on priority
    insert_at = len(callbacks)
    for i, existing_callback in enumerate(callbacks):
        if callback.priority < existing_callback.priority:
            insert_at = i
            break

    callbacks.insert(insert_at, callback)
