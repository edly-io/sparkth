"""Domain exceptions raised when plugins contribute LMS content."""


class ContentBuildError(Exception):
    """Raised by a :class:`ContentContributor`'s ``build`` when it cannot produce its block.

    A publishing tool resolves the failure through its own error contract (for example,
    Open edX's ``openedx_add_plugin_content`` returns an ``{"error": {...}}`` dict) instead of
    letting the exception propagate as a raw, unhandled failure.
    """


class ContentPlacementError(Exception):
    """Raised by a :class:`ContentContributor`'s ``on_placed`` when it cannot record a placement.

    The block already exists in the course by then. A publishing tool reports the failure with
    the block's locator through its own error contract, and leaves the block's attributes
    unwritten, so the block does not reference content whose placement went unrecorded.
    """


class UnknownContentContributorError(Exception):
    """Raised when no content contributor is registered under the requested name."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Unknown content contributor: {name}")


class ContentContributorUnavailableError(Exception):
    """Raised when the requested contributor's plugin is switched off for the caller.

    The contributor is registered, so the caller is told it may not be used rather than that it
    does not exist.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Content contributor {name!r} is unavailable: its plugin is switched off")


class DuplicateContentContributorError(Exception):
    """Raised when a contributor claims a name that a different value or plugin already holds.

    Fires only for a *different* contributor, or one from a different plugin, claiming the
    name, which is a programming error: a publishing tool resolves by name, so two contributors
    under one name would leave it unclear which to build and whose switch applies. An equal
    contributor from another construction of the same plugin is accepted, so a plugin
    constructed more than once does not trip this.

    Raising this from a plugin's ``__init__`` does not stop the process. The plugin loader
    logs a failed construction and carries on, so the colliding plugin is absent from the
    running application — no routes, no tools, no contributor — while everything else
    starts normally. The log entry is the only signal.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"A different content contributor is already registered as '{name}'")
