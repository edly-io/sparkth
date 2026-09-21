"""Domain exceptions raised when plugins contribute LMS content."""


class ContentBuildError(Exception):
    """Raised by a :class:`ContentContributor`'s ``build`` when it cannot produce its block.

    A publishing tool resolves the failure through its own error contract (for example,
    Open edX's ``openedx_add_plugin_content`` returns an ``{"error": {...}}`` dict) instead of
    letting the exception propagate as a raw, unhandled failure.
    """


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
