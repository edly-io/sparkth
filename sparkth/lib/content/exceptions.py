"""Domain exceptions raised when plugins contribute LMS content."""


class DuplicateContentContributorError(Exception):
    """Raised when a contributor claims a name an unequal contributor already holds.

    Fires only for a *different* contributor claiming the name, which is a programming
    error: a publishing tool resolves by name, so two unequal contributors under one name
    would have it build whichever registered first. Re-registering an equal contributor is
    a no-op, so a plugin constructed more than once does not trip this.

    Raising this from a plugin's ``__init__`` does not stop the process. The plugin loader
    logs a failed construction and carries on, so the colliding plugin is absent from the
    running application — no routes, no tools, no contributor — while everything else
    starts normally. The log entry is the only signal.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"A different content contributor is already registered as '{name}'")
