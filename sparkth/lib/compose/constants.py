"""Constants for Compose agents."""

import re
from typing import Final

# The name of the tool Compose's planner refuses a message with.
REFUSE_TOOL_NAME: Final = "refuse"

# Names Compose keeps for itself.
RESERVED_AGENT_NAMES: Final = frozenset({"compose", "operator", REFUSE_TOOL_NAME})

# An agent's name is the tool name Compose calls it by.
AGENT_NAME_PATTERN: Final = re.compile(r"^[a-z][a-z0-9_]*$")
