"""Domain exceptions raised when plugins contribute LMS content."""


class DuplicateContentContributorError(Exception):
    """Raised when a contributor claims a name an unequal contributor already holds.

    Fires only for a *different* contributor claiming the name — a startup-fatal
    programming error, because a publishing tool resolves by name and would otherwise
    build whichever of the two happened to register first. Re-registering an equal
    contributor is a no-op, so a plugin constructed more than once does not trip this.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"A different content contributor is already registered as '{name}'")
