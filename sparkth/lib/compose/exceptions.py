"""Domain exceptions raised when plugins contribute Compose agents.

Each is a programming error raised from a plugin's ``__init__``.
"""


class InvalidAgentName(Exception):
    """Raised when an agent's name can't be used as a tool name."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(
            f"Agent name '{name}' must start with a letter and use only lowercase letters, digits and underscores"
        )


class ReservedAgentName(Exception):
    """Raised when an agent claims a name Compose keeps for itself."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Agent name '{name}' is reserved")


class DuplicateAgentName(Exception):
    """Raised when another agent, another plugin or a registered MCP tool already holds the name.

    An equal agent from the same plugin is accepted, so a plugin constructed more than once doesn't
    trip this.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Agent name '{name}' is already taken")


class DuplicateAgentTool(Exception):
    """Raised when two of an agent's tools share a name."""

    def __init__(self, agent_name: str, tool_name: str) -> None:
        self.agent_name = agent_name
        self.tool_name = tool_name
        super().__init__(f"Agent '{agent_name}' has more than one tool named '{tool_name}'")
