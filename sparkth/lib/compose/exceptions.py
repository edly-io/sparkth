"""Domain exceptions raised when plugins contribute Compose agents.

Each is a programming error raised from a plugin's ``__init__``.
"""


class DuplicateAgentTitle(Exception):
    """Raised when a different agent already holds the title.

    An equal agent arriving again is accepted, so a plugin constructed more than once doesn't trip
    this.
    """

    def __init__(self, title: str) -> None:
        self.title = title
        super().__init__(f"A different agent is already registered as '{title}'")
