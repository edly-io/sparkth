"""Exceptions a tool raises for the agent that called it."""


class ToolFailure(Exception):
    """A failure a tool reports on purpose, for the agent that called it to act on.

    ``str()`` is written for that agent: it says what was wrong with the work it submitted and what
    to change, and holds nothing about how the server works. A surface that runs tools for an agent
    hands it this text. Any other exception a tool raises is unplanned, and the agent is told only
    that the tool failed.
    """
