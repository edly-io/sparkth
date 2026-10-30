"""Domain exceptions raised when plugins contribute chat capabilities."""


class DuplicateChatCapabilityError(Exception):
    """Raised when a capability claims a title an unequal capability already holds.

    Fires only for a *different* capability claiming the title, which is a programming error:
    chat's system prompt and the scope classifier's list each capability under its title, so two
    unequal capabilities under one title would give the model two sections under one heading. An
    equal capability arriving again is accepted, so a plugin constructed more than once does not
    trip this.

    Raising this from a plugin's ``__init__`` does not stop the process. The plugin loader logs a
    failed construction and carries on, so the colliding plugin is absent from the running
    application — no routes, no tools, no capability — while everything else starts normally.
    The log entry is the only signal.
    """

    def __init__(self, title: str) -> None:
        self.title = title
        super().__init__(f"A different chat capability is already registered as '{title}'")
